import os

from django.conf import settings
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from .metrics import (
    get_backlog_health,
    get_dashboard_summary,
    get_flow_metrics,
    get_pr_metrics,
    get_sprint_metrics,
)
from .models import (
    Attachment,
    Comment,
    CustomField,
    CustomFieldValue,
    Epic,
    OutgoingWebhook,
    RecurrenceRule,
    SavedSearch,
    Sprint,
    Subtask,
    Task,
    TaskActivity,
    TaskApproval,
    TaskRelation,
    TaskTemplate,
    TimeEntry,
)
from .serializers import (
    AttachmentSerializer,
    CommentSerializer,
    CustomFieldSerializer,
    CustomFieldValueSerializer,
    EpicSerializer,
    OutgoingWebhookSerializer,
    RecurrenceRuleSerializer,
    SavedSearchSerializer,
    SprintSerializer,
    SubtaskSerializer,
    TaskActivitySerializer,
    TaskApprovalSerializer,
    TaskCreateUpdateSerializer,
    TaskRelationSerializer,
    TaskSerializer,
    TaskTemplateSerializer,
    TimeEntrySerializer,
)


class TaskCreateUpdateViewSetMixin:
    """Devuelve la representación completa tras create/update."""

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        full = TaskSerializer(serializer.instance, context=self.get_serializer_context())
        headers = self.get_success_headers(full.data)
        return Response(full.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        full = TaskSerializer(serializer.instance, context=self.get_serializer_context())
        return Response(full.data)


class TaskViewSet(TaskCreateUpdateViewSetMixin, viewsets.ModelViewSet):
    """CRUD de tareas con filtros por estado, prioridad, etiqueta, proyecto, sprint, épica, tipo."""

    filterset_fields = [
        "state", "priority", "project", "tags", "task_type",
        "sprint", "epic", "parent", "section", "is_milestone",
    ]
    search_fields = ["title", "description"]
    ordering_fields = [
        "created_at", "updated_at", "due_date", "priority", "title",
        "start_date", "story_points", "position", "is_pinned",
        "is_milestone",
    ]

    def get_queryset(self):
        # select_related para FKs del serializer (sprint_name, epic_title,
        # parent_title, assignee_email, recurrence); prefetch para las
        # colecciones que el serializer recorre por tarea — evita N+1 en
        # list (comments, activities, relations, subtasks_children)
        from django.db.models import (
            Count,
            IntegerField,
            OuterRef,
            Prefetch,
            Subquery,
            Sum,
        )
        from django.db.models.functions import Coalesce
        qs = Task.objects.for_user(self.request.user).select_related(
            "project", "sprint", "epic", "parent", "assignee", "owner",
            "recurrence", "section",
        ).prefetch_related(
            "tags", "subtasks", "assignees", "watchers", "favorited_by",
            "approvals__requester", "approvals__approver",
            Prefetch(
                "comments",
                queryset=Comment.objects.select_related("author").annotate(
                    replies_count_ann=Count("replies", distinct=True)
                ),
            ),
            "activities", "activities__actor",
            "outgoing_relations__source", "outgoing_relations__target",
            "subtasks_children",
        ).annotate(
            # Subquery (no join): un Sum sobre join se inflaría con el
            # fan-out de los joins de for_user (members/assignees/watchers)
            logged_seconds_ann=Coalesce(
                Subquery(
                    TimeEntry.objects.filter(task=OuterRef("pk"))
                    .order_by()
                    .values("task")
                    .annotate(s=Sum("duration_seconds"))
                    .values("s"),
                    output_field=IntegerField(),
                ),
                0,
            )
        )
        from .selectors import apply_task_filters
        qs = apply_task_filters(qs, self.request.query_params)
        # Favoritos es por-usuario (M2M), no expresable via filterset
        if self.request.query_params.get("favorite") == "true":
            qs = qs.filter(favorited_by=self.request.user)
        # "Mías": asignada o co-asignada al usuario actual
        if self.request.query_params.get("mine") == "true":
            from django.db.models import Q as _Q
            qs = qs.filter(
                _Q(assignee=self.request.user)
                | _Q(assignees=self.request.user)
            ).distinct()
        return qs

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return TaskCreateUpdateSerializer
        return TaskSerializer

    def get_object(self):
        """Lectura: tareas propias o de proyectos compartidos.
        Escritura: requiere rol editor/owner en el proyecto."""
        obj = super().get_object()
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            from .policies import assert_can_write_task
            assert_can_write_task(self.request.user, obj)
        return obj

    def perform_create(self, serializer):
        from django.db.models import Max
        next_pos = (
            Task.objects.for_user(self.request.user).aggregate(
                m=Max("position")
            )["m"]
            or 0
        ) + 1
        # seq por proyecto para la ref legible ("MP-12"); sin proyecto
        # queda en 0 y el ref cae al id (Task.seq no es único: los
        # updates masivos podrían colisionar transitoriamente).
        project = serializer.validated_data.get("project")
        seq = 0
        if project is not None:
            seq = (
                Task.objects.filter(project=project).aggregate(
                    m=Max("seq")
                )["m"]
                or 0
            ) + 1
        serializer.save(
            owner=self.request.user, position=next_pos, seq=seq
        )

    def perform_update(self, serializer):
        # El serializer (TaskCreateUpdateSerializer.update) ya registra
        # TaskActivity para cambios de state/priority/sprint/parent.
        instance = serializer.save()
        from .services import apply_completion_effects
        apply_completion_effects(instance)

    @action(detail=True, methods=["post"])
    def subtasks(self, request, pk=None):
        task = self.get_object()
        serializer = SubtaskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(task=task)
        TaskActivity.objects.create(
            task=task, actor=request.user,
            action=TaskActivity.ActionType.SUBTASK_ADDED,
            new_value=serializer.data["title"],
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def comments(self, request, pk=None):
        task = self.get_object()
        # Validar que el padre pertenece a esta tarea (threading)
        parent_id = request.data.get("parent")
        if parent_id:
            parent = Comment.objects.filter(
                id=parent_id, task=task
            ).first()
            if parent is None:
                return Response(
                    {"parent": "El comentario padre debe ser de esta tarea."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        serializer = CommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(task=task, author=request.user)
        TaskActivity.objects.create(
            task=task, actor=request.user,
            action=TaskActivity.ActionType.COMMENTED,
            new_value=serializer.data["body"][:200],
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    # --- Watchers ---

    def _get_readable_task(self, pk):
        """Tarea con acceso de LECTURA para el usuario (404 si no la ve).

        A diferencia de get_object(), no exige permiso de escritura: los
        endpoints de watch/timer_status son acciones de lectura que un
        watcher o viewer también puede usar.
        """
        from django.shortcuts import get_object_or_404
        return get_object_or_404(
            Task.objects.for_user(self.request.user), pk=pk
        )

    @action(detail=True, methods=["post"])
    def watch(self, request, pk=None):
        """Empieza a seguir la tarea (idempotente)."""
        task = self._get_readable_task(pk)
        task.watchers.add(request.user)
        return Response({"watching": True})

    @action(detail=True, methods=["post", "delete"])
    def unwatch(self, request, pk=None):
        """Deja de seguir la tarea (idempotente)."""
        task = self._get_readable_task(pk)
        task.watchers.remove(request.user)
        return Response({"watching": False})

    @action(detail=True, methods=["post"])
    def favorite(self, request, pk=None):
        """Marca la tarea como favorita del usuario (idempotente)."""
        task = self._get_readable_task(pk)
        task.favorited_by.add(request.user)
        return Response({"favorite": True})

    @action(detail=True, methods=["post", "delete"])
    def unfavorite(self, request, pk=None):
        """Quita la tarea de favoritos (idempotente)."""
        task = self._get_readable_task(pk)
        task.favorited_by.remove(request.user)
        return Response({"favorite": False})

    # --- Cronómetro en vivo ---

    @staticmethod
    def _stop_entry(entry, now):
        """Detiene una entrada running y calcula su duración."""
        entry.ended_at = now
        entry.is_running = False
        if entry.started_at:
            entry.duration_seconds = max(
                int((now - entry.started_at).total_seconds()), 1
            )
        else:
            entry.duration_seconds = max(entry.duration_seconds, 1)
        entry.save(
            update_fields=["ended_at", "is_running", "duration_seconds"]
        )
        return entry

    @action(detail=True, methods=["post"], url_path="timer_start")
    def timer_start(self, request, pk=None):
        """Inicia el cronómetro del usuario en esta tarea.

        Requiere permiso de escritura (get_object). Si el usuario ya tiene
        otra entrada running en cualquier tarea, se detiene automáticamente
        (solo un timer activo por usuario).
        """
        task = self.get_object()
        now = timezone.now()
        for entry in TimeEntry.objects.filter(
            user=request.user, is_running=True
        ):
            self._stop_entry(entry, now)
        entry = TimeEntry.objects.create(
            task=task,
            user=request.user,
            is_running=True,
            started_at=now,
        )
        return Response(
            TimeEntrySerializer(entry).data, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["post"], url_path="timer_stop")
    def timer_stop(self, request, pk=None):
        """Detiene el cronómetro del usuario en esta tarea (404 si no hay)."""
        task = self.get_object()
        entry = TimeEntry.objects.filter(
            task=task, user=request.user, is_running=True
        ).first()
        if entry is None:
            return Response(
                {"error": "No hay un cronómetro en marcha en esta tarea"},
                status=status.HTTP_404_NOT_FOUND,
            )
        self._stop_entry(entry, timezone.now())
        return Response(TimeEntrySerializer(entry).data)

    @action(detail=True, methods=["get"], url_path="timer_status")
    def timer_status(self, request, pk=None):
        """Estado del cronómetro del usuario en esta tarea."""
        task = self._get_readable_task(pk)
        entry = TimeEntry.objects.filter(
            task=task, user=request.user, is_running=True
        ).first()
        return Response({
            "running": entry is not None,
            "started_at": entry.started_at if entry else None,
        })

    # --- Aprobaciones (paridad Asana/Monday) ---

    @action(detail=True, methods=["post"], url_path="request_approval")
    def request_approval(self, request, pk=None):
        """Solicita la aprobación de la tarea a otro usuario.

        Requiere acceso de ESCRITURA a la tarea (get_object lo exige en
        POST). El approver debe tener al menos acceso de lectura al
        proyecto de la tarea; si la tarea no tiene proyecto, cualquier
        usuario activo vale. Crea un TaskApproval pending y notifica al
        approver (type "approval_request").
        """
        task = self.get_object()
        approver_id = request.data.get("approver")
        if not approver_id:
            return Response(
                {"approver": "Este campo es obligatorio."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from django.contrib.auth import get_user_model
        approver = (
            get_user_model()
            .objects.filter(id=approver_id, is_active=True)
            .first()
        )
        if approver is None:
            return Response(
                {"approver": "Usuario no encontrado o inactivo."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if task.project_id is not None:
            from apps.projects.models import accessible_projects
            if not accessible_projects(approver).filter(
                id=task.project_id
            ).exists():
                return Response(
                    {
                        "approver": (
                            "El aprobador no tiene acceso al proyecto "
                            "de la tarea."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        approval = TaskApproval.objects.create(
            task=task,
            requester=request.user,
            approver=approver,
            note=request.data.get("note", "") or "",
        )
        from apps.notifications.services import notify
        notify(
            recipient=approver,
            notification_type="approval_request",
            title=f"Aprobación solicitada: {task.title}",
            body=(
                f"{request.user.email} solicita tu aprobación"
                + (f" — {approval.note}" if approval.note else "")
            ),
            task=task,
            action_url=f"/app/tasks?task={task.id}",
        )
        return Response(
            TaskApprovalSerializer(approval).data,
            status=status.HTTP_201_CREATED,
        )

    def _decide_approval(self, request, pk, new_status):
        """Lógica común de approve/reject sobre el último pending.

        404 si la tarea no es visible o no hay approval pendiente;
        403 si hay uno pendiente pero el usuario no es su approver.
        """
        task = self._get_readable_task(pk)
        approval = task.approvals.filter(
            status=TaskApproval.Status.PENDING
        ).first()
        if approval is None:
            return Response(
                {"error": "No hay una aprobación pendiente en esta tarea"},
                status=status.HTTP_404_NOT_FOUND,
            )
        if approval.approver_id != request.user.id:
            raise PermissionDenied(
                "Solo el aprobador asignado puede decidir esta solicitud"
            )
        approval.status = new_status
        approval.decision_note = request.data.get("note", "") or ""
        approval.decided_at = timezone.now()
        approval.save(
            update_fields=["status", "decision_note", "decided_at"]
        )
        from apps.notifications.services import notify
        verb = (
            "aprobada"
            if new_status == TaskApproval.Status.APPROVED
            else "rechazada"
        )
        notify(
            recipient=approval.requester,
            notification_type="approval_decision",
            title=f"Solicitud {verb}: {task.title}",
            body=(
                f"{request.user.email} ha {verb} tu solicitud"
                + (
                    f" — {approval.decision_note}"
                    if approval.decision_note
                    else ""
                )
            ),
            task=task,
            action_url=f"/app/tasks?task={task.id}",
        )
        return Response(TaskApprovalSerializer(approval).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        """Aprueba el último approval pendiente (solo su approver)."""
        return self._decide_approval(
            request, pk, TaskApproval.Status.APPROVED
        )

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        """Rechaza el último approval pendiente (solo su approver)."""
        return self._decide_approval(
            request, pk, TaskApproval.Status.REJECTED
        )

    @action(detail=True, methods=["get"])
    def activities(self, request, pk=None):
        task = self.get_object()
        activities = task.activities.all()[:50]
        serializer = TaskActivitySerializer(activities, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get", "post"])
    def relations(self, request, pk=None):
        task = self.get_object()
        if request.method == "GET":
            rels = task.outgoing_relations.all() | task.incoming_relations.all()
            serializer = TaskRelationSerializer(rels, many=True)
            return Response(serializer.data)
        # POST: crear relación (source pasa por contexto para que validate()
        # pueda comprobar auto-relación y dependencias circulares)
        serializer = TaskRelationSerializer(
            data=request.data,
            context={"request": request, "source": task},
        )
        serializer.is_valid(raise_exception=True)
        target_id = serializer.validated_data["target"].id
        # Verificar que target es editable por el usuario
        if not Task.objects.for_user(request.user, write=True).filter(id=target_id).exists():
            return Response(
                {"error": "La tarea objetivo no existe o no te pertenece"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer.save(source=task)
        TaskActivity.objects.create(
            task=task, actor=request.user,
            action=TaskActivity.ActionType.RELATION_ADDED,
            new_value=f"{serializer.validated_data['relation_type']} -> {target_id}",
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def move_to_sprint(self, request, pk=None):
        task = self.get_object()
        sprint_id = request.data.get("sprint_id")
        if not sprint_id:
            return Response(
                {"error": "sprint_id requerido"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            from django.db.models import Q

            from apps.projects.models import accessible_projects
            sprint = Sprint.objects.get(
                Q(owner=request.user)
                | Q(project__in=accessible_projects(request.user, write=True)),
                id=sprint_id,
            )
        except Sprint.DoesNotExist:
            return Response(
                {"error": "Sprint no encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )
        # Coherencia: el sprint debe ser del mismo proyecto que la tarea
        if sprint.project_id and sprint.project_id != task.project_id:
            return Response(
                {"error": "El sprint pertenece a otro proyecto"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        old_sprint = task.sprint
        task.sprint = sprint
        task.save(update_fields=["sprint"])
        TaskActivity.objects.create(
            task=task, actor=request.user,
            action=TaskActivity.ActionType.SPRINT_CHANGED,
            old_value=str(old_sprint) if old_sprint else "",
            new_value=sprint.name,
        )
        return Response({"message": f"Tarea movida a {sprint.name}"})

    # --- Métricas ---

    @action(detail=False, methods=["get"])
    def metrics_flow(self, request):
        """Métricas de flujo: lead time, cycle time, throughput, WIP."""
        from django.core.cache import cache
        try:
            days = min(max(int(request.query_params.get("days", 30)), 1), 365)
        except (TypeError, ValueError):
            days = 30
        cache_key = f"metrics_flow:{request.user.id}:{days}"
        data = cache.get(cache_key)
        if data is None:
            data = get_flow_metrics(request.user, days)
            cache.set(cache_key, data, timeout=120)  # 2 min
        return Response(data)

    @action(detail=False, methods=["get"])
    def metrics_backlog(self, request):
        """Salud del backlog."""
        from django.core.cache import cache
        cache_key = f"metrics_backlog:{request.user.id}"
        data = cache.get(cache_key)
        if data is None:
            data = get_backlog_health(request.user)
            cache.set(cache_key, data, timeout=120)
        return Response(data)

    @action(detail=False, methods=["get"])
    def metrics_dashboard(self, request):
        """Dashboard general: resumen ejecutivo."""
        from django.core.cache import cache
        cache_key = f"metrics_dashboard:{request.user.id}"
        data = cache.get(cache_key)
        if data is None:
            data = get_dashboard_summary(request.user)
            cache.set(cache_key, data, timeout=60)  # 1 min
        return Response(data)

    @action(detail=False, methods=["get"])
    def metrics_prs(self, request):
        """Métricas de pull requests."""
        from django.core.cache import cache
        cache_key = f"metrics_prs:{request.user.id}"
        data = cache.get(cache_key)
        if data is None:
            data = get_pr_metrics(request.user)
            cache.set(cache_key, data, timeout=120)
        return Response(data)

    # Campos que bulk_update puede tocar — whitelist explícita para evitar
    # mass assignment (owner, version, completed_at, etc. quedan prohibidos)
    BULK_UPDATE_ALLOWED_FIELDS = {
        "title", "description", "priority", "state", "due_date",
        "sprint", "epic", "project", "parent", "assignee",
        "estimated_hours", "story_points", "is_pinned", "is_milestone",
    }
    BULK_MAX_TASKS = 200
    REORDER_MAX_TASKS = 500

    @action(detail=False, methods=["post"])
    def reorder(self, request):
        """Asigna ``position`` secuencial según el orden de ``task_ids``.

        Orden manual de la vista de lista (drag & drop). Solo afecta a
        tareas con acceso de escritura; ids inaccesibles → 404.
        """
        task_ids = request.data.get("task_ids")
        if not isinstance(task_ids, list) or not task_ids:
            return Response(
                {"error": "task_ids es requerido"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(task_ids) > self.REORDER_MAX_TASKS:
            return Response(
                {"error": f"Máximo {self.REORDER_MAX_TASKS} tareas por operación"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        writable = {
            t.id: t
            for t in Task.objects.for_user(request.user, write=True).filter(
                id__in=task_ids
            )
        }
        missing = [i for i in task_ids if i not in writable]
        if missing:
            return Response(
                {"error": f"Tareas inaccesibles o inexistentes: {missing[:5]}"},
                status=status.HTTP_404_NOT_FOUND,
            )
        for pos, tid in enumerate(task_ids):
            writable[tid].position = pos
        Task.objects.bulk_update(writable.values(), ["position"])
        return Response({"updated": len(task_ids)})

    @action(detail=False, methods=["post"])
    def bulk_update(self, request):
        """Actualiza múltiples tareas a la vez."""
        task_ids = request.data.get("task_ids", [])
        updates = request.data.get("updates", {})
        if not task_ids or not updates:
            return Response(
                {"error": "task_ids y updates son requeridos"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not isinstance(task_ids, list) or len(task_ids) > self.BULK_MAX_TASKS:
            return Response(
                {"error": f"Máximo {self.BULK_MAX_TASKS} tareas por operación"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not isinstance(updates, dict):
            return Response({"error": "updates debe ser un objeto"}, status=status.HTTP_400_BAD_REQUEST)
        disallowed = set(updates) - self.BULK_UPDATE_ALLOWED_FIELDS
        if disallowed:
            return Response(
                {"error": f"Campos no permitidos: {sorted(disallowed)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Validar valores por campo
        if "state" in updates and updates["state"] not in [c[0] for c in Task.State.choices]:
            return Response({"error": "state inválido"}, status=status.HTTP_400_BAD_REQUEST)
        if "priority" in updates and updates["priority"] not in [c[0] for c in Task.Priority.choices]:
            return Response({"error": "priority inválida"}, status=status.HTTP_400_BAD_REQUEST)
        # Validar FKs: los destinos deben ser editables por el usuario
        from apps.projects.models import accessible_projects
        editable_projects = accessible_projects(request.user, write=True)
        if updates.get("sprint") and not Sprint.objects.filter(
            id=updates["sprint"], project__in=editable_projects
        ).exists():
            return Response({"error": "Sprint no válido"}, status=status.HTTP_400_BAD_REQUEST)
        if updates.get("project") and not editable_projects.filter(id=updates["project"]).exists():
            return Response({"error": "Proyecto no válido"}, status=status.HTTP_400_BAD_REQUEST)
        if updates.get("epic"):
            from django.db.models import Q

            from .models import Epic
            if not Epic.objects.filter(
                Q(owner=request.user) | Q(project__in=editable_projects),
                id=updates["epic"],
            ).exists():
                return Response({"error": "Epic no válida"}, status=status.HTTP_400_BAD_REQUEST)
        if updates.get("parent") and not Task.objects.for_user(
            request.user, write=True
        ).filter(id=updates["parent"]).exists():
            return Response({"error": "Tarea padre no válida"}, status=status.HTTP_400_BAD_REQUEST)
        qs = Task.objects.for_user(request.user, write=True).filter(id__in=task_ids)
        # Respetar workflows: si el estado cambia, cada tarea con proyecto
        # que tenga transiciones definidas debe poder seguir la arista.
        if "state" in updates:
            from apps.projects.models import WorkflowTransition
            new_state = updates["state"]
            for task in qs.filter(project__isnull=False).only("id", "state", "project"):
                trans = WorkflowTransition.objects.filter(project_id=task.project_id)
                if trans.exists() and task.state != new_state and not trans.filter(
                    from_state=task.state, to_state=new_state
                ).exists():
                    return Response(
                        {"error": f"La tarea #{task.id} no permite {task.state} → {new_state} por el workflow del proyecto"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
        if updates.get("assignee"):
            from django.contrib.auth import get_user_model
            from django.db.models import Q as _Q
            assignee = get_user_model().objects.filter(id=updates["assignee"]).first()
            if not assignee:
                return Response({"error": "Assignee no válido"}, status=status.HTTP_400_BAD_REQUEST)
            # El assignee debe tener acceso a los proyectos de TODAS las tareas
            assignee_projects = accessible_projects(assignee)
            if qs.exclude(_Q(project__isnull=True) | _Q(project__in=assignee_projects)).exists():
                return Response(
                    {"error": "El assignee no tiene acceso a todos los proyectos afectados"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # Tareas sin proyecto: solo auto-asignación
            if assignee.id != request.user.id and qs.filter(project__isnull=True).exists():
                return Response(
                    {"error": "Solo puedes asignarte tareas sin proyecto"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        # Efectos derivados del cambio de estado (qs.update no dispara save()):
        # completed_at debe reflejar completed/reapertura igual que en
        # update individual, GraphQL y sync.
        if updates.get("state") == Task.State.COMPLETED:
            updates["completed_at"] = timezone.now()
            # Las recurrentes completadas generan la siguiente ocurrencia
            for t in qs.filter(recurrence__isnull=False):
                t.generate_next_occurrence()
        elif updates.get("state"):
            updates["completed_at"] = None
        updated = qs.update(**updates)
        return Response({"updated": updated})

    @action(detail=False, methods=["get"])
    def search(self, request):
        """Búsqueda full-text sobre tareas."""
        from django.db.models import Q

        query = request.query_params.get("q", "").strip()
        if not query:
            return Response({"results": [], "count": 0})

        # Las tareas vinculadas a un EncryptedTask (E2E) no deben indexarse
        # en texto claro: si el cliente ligó una Task con contenido real, el
        # FTS la expondría por plaintext — se excluyen de la búsqueda.
        qs = Task.objects.for_user(request.user).exclude(
            encrypted_data__isnull=False
        )
        from django.db import connection
        if connection.vendor == "postgresql":
            # FTS sobre la columna indexada search_vector (GIN): el trigger la
            # mantiene con vectores 'spanish'+'english'. plainto_tsquery con
            # 'simple' evita stemming para que case contra ambos idiomas.
            from django.db.models.expressions import RawSQL
            qs = (
                qs.annotate(
                    rank=RawSQL(
                        "ts_rank(search_vector, plainto_tsquery('simple', %s))",
                        (query,),
                    )
                )
                .filter(
                    pk__in=Task.objects.extra(
                        where=["search_vector @@ plainto_tsquery('simple', %s)"],
                        params=[query],
                    ).values("pk")
                )
                .order_by("-rank")
            )
        else:
            # Fallback compatible con SQLite (tests/desarrollo)
            qs = qs.filter(
                Q(title__icontains=query) | Q(description__icontains=query)
            )
        qs = qs.select_related("project", "sprint").prefetch_related("tags")[:50]

        serializer = self.get_serializer(qs, many=True)
        return Response({"results": serializer.data, "count": len(serializer.data)})

    @action(detail=False, methods=["get"])
    def gantt(self, request):
        """Datos para vista Gantt."""
        from django.core.cache import cache

        from .advanced_metrics import get_gantt_data
        cache_key = f"gantt:{request.user.id}"
        data = cache.get(cache_key)
        if data is None:
            data = get_gantt_data(request.user)
            cache.set(cache_key, data, timeout=120)
        return Response(data)

    @action(detail=False, methods=["get"])
    def burndown(self, request):
        """Datos para burndown chart de un sprint."""
        from .advanced_metrics import get_burndown_data
        sprint_id = request.query_params.get("sprint_id")
        if not sprint_id:
            return Response({"error": "sprint_id requerido"}, status=400)
        data = get_burndown_data(request.user, sprint_id)
        if data is None:
            return Response({"error": "Sprint no encontrado"}, status=404)
        return Response(data)

    @action(detail=True, methods=["get"])
    def dependencies(self, request, pk=None):
        """Grafo de dependencias de la tarea.

        - blocked_by: relaciones BLOCKS/DEPENDS_ON cuyo source sigue abierto
          (esta tarea está bloqueada por ellas).
        - blocks: tareas que esta tarea bloquea.
        - related: relaciones bidireccionales no bloqueantes.
        """
        task = self.get_object()
        from .models import TaskRelation

        OPEN = ["pending", "in_progress", "review", "blocked"]
        blocking_types = [
            TaskRelation.RelationType.BLOCKS,
            TaskRelation.RelationType.DEPENDS_ON,
        ]

        incoming = task.incoming_relations.select_related("source")
        outgoing = task.outgoing_relations.select_related("target")

        blocked_by = [{
            "task_id": r.source_id, "title": r.source.title,
            "state": r.source.state, "relation": r.relation_type,
        } for r in incoming
            if r.relation_type in blocking_types and r.source.state in OPEN]

        blocks = [{
            "task_id": r.target_id, "title": r.target.title,
            "state": r.target.state, "relation": r.relation_type,
        } for r in outgoing
            if r.relation_type in blocking_types]

        related = [{
            "task_id": r.source_id if r.target_id == task.id else r.target_id,
            "title": (r.source.title if r.target_id == task.id
                      else r.target.title),
            "relation": r.relation_type,
        } for r in list(incoming) + list(outgoing)
            if r.relation_type not in blocking_types]

        return Response({
            "task_id": task.id,
            "is_blocked": len(blocked_by) > 0,
            "blocked_by": blocked_by,
            "blocks": blocks,
            "related": related,
        })

    @action(detail=False, methods=["get"], url_path="global-search")
    def global_search(self, request):
        """Búsqueda global con sintaxis: tasks + comments + wiki + projects.

        ``/api/tasks/global-search/?q=assigned:me status:open "oauth"``
        """
        from .global_search import global_search as _gs
        q = request.query_params.get("q", "").strip()
        if not q:
            return Response({"error": "q requerido"}, status=400)
        return Response(_gs(request.user, q))

    @action(
        detail=False, methods=["get"], url_path="calendar.ics",
        permission_classes=[],
    )
    def calendar_feed(self, request):
        """Feed iCal (RFC 5545) con los deadlines de las tareas.

        Suscribible desde Google Calendar/Outlook/Apple Calendar. Estos
        clientes no envían cookies ni JWT, así que el feed se autentica con
        un token opaco por URL (?token=...) generado en
        POST /api/users/me/calendar_token/. La sesión normal también vale.
        """
        from django.contrib.auth import get_user_model
        from django.http import HttpResponse

        user = request.user
        if not user.is_authenticated:
            token = request.query_params.get("token", "")
            if not token:
                return HttpResponse(status=401)
            user = get_user_model().objects.filter(
                ical_token=token, is_active=True
            ).first()
            if not user:
                return HttpResponse(status=401)

        tasks = Task.objects.for_user(user).filter(
            due_date__isnull=False
        ).exclude(state__in=["cancelled", "archived"])[:500]

        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//TODOlist//Task Calendar//ES",
            "CALSCALE:GREGORIAN",
            "X-WR-CALNAME:TODOlist Tasks",
        ]
        for t in tasks:
            dt = t.due_date.strftime("%Y%m%dT%H%M%SZ")
            uid = f"task-{t.id}@todolist"
            title = t.title.replace("\\", "\\\\").replace(
                ",", "\\,").replace(";", "\\;").replace("\n", "\\n")
            lines += [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{t.created_at.strftime('%Y%m%dT%H%M%SZ')}",
                f"DTSTART:{dt}",
                f"SUMMARY:{title} [{t.state}]",
                "END:VEVENT",
            ]
        lines.append("END:VCALENDAR")
        return HttpResponse(
            "\r\n".join(lines), content_type="text/calendar; charset=utf-8"
        )

    @action(detail=False, methods=["get"], url_path="my-work")
    def my_work(self, request):
        """Vista 'Mi trabajo': lo que el usuario necesita ver al abrir la app.

        Devuelve tareas asignadas al usuario agrupadas por urgencia:
        overdue, due_today, in_progress, blocked (con blocker), upcoming.
        """
        user = request.user
        now = timezone.now()
        from django.db.models import Q
        base = Task.objects.for_user(user).filter(
            Q(assignee=user) | Q(assignees=user)
        ).exclude(
            state__in=["completed", "cancelled", "archived"]
        ).select_related("project", "sprint").distinct()

        def _serialize(qs):
            return [{
                "id": t.id, "title": t.title, "state": t.state,
                "priority": t.priority, "due_date": t.due_date,
                "project": t.project.name if t.project else None,
            } for t in qs[:20]]

        # Tareas que bloquean a otras del usuario (dependencias blocks)
        from .models import TaskRelation
        blocked_relations = TaskRelation.objects.filter(
            target__in=base,
            relation_type=TaskRelation.RelationType.BLOCKS,
            source__state__in=["pending", "in_progress", "review", "blocked"],
        ).select_related("source", "target")
        blocked_ids = set()
        blockers = {}
        for rel in blocked_relations:
            blocked_ids.add(rel.target_id)
            blockers.setdefault(rel.target_id, []).append(
                {"id": rel.source_id, "title": rel.source.title,
                 "state": rel.source.state}
            )

        def _group(qs):
            out = _serialize(qs)
            for item in out:
                if item["id"] in blockers:
                    item["blocked_by"] = blockers[item["id"]]
            return out

        return Response({
            "overdue": _group(base.filter(due_date__lt=now)),
            "due_today": _group(base.filter(
                due_date__gte=now.replace(hour=0, minute=0),
                due_date__lt=now.replace(hour=0, minute=0) + timezone.timedelta(days=1),
            )),
            "in_progress": _group(base.filter(state="in_progress")),
            "blocked": _group(base.filter(id__in=blocked_ids)),
            "upcoming": _group(base.filter(
                due_date__gte=now + timezone.timedelta(days=1),
                due_date__lte=now + timezone.timedelta(days=7),
            )),
        })

    @action(detail=False, methods=["get"])
    def burnup(self, request):
        """Datos para burnup chart: completado vs scope en el tiempo."""
        from .advanced_metrics import get_burnup_data
        sprint_id = request.query_params.get("sprint_id")
        if not sprint_id:
            return Response({"error": "sprint_id requerido"}, status=400)
        data = get_burnup_data(request.user, sprint_id)
        if data is None:
            return Response({"error": "Sprint no encontrado"}, status=404)
        return Response(data)

    @action(detail=False, methods=["get"])
    def capacity(self, request):
        """Datos de capacity planning."""
        from django.core.cache import cache

        from .advanced_metrics import get_capacity_data
        cache_key = f"capacity:{request.user.id}"
        data = cache.get(cache_key)
        if data is None:
            data = get_capacity_data(request.user)
            cache.set(cache_key, data, timeout=120)
        return Response(data)

    @action(detail=False, methods=["get"])
    def roadmap(self, request):
        """Roadmap/Timeline: épicas con rangos temporales y progreso."""
        from django.core.cache import cache

        from .advanced_metrics import get_roadmap_data
        cache_key = f"roadmap:{request.user.id}"
        data = cache.get(cache_key)
        if data is None:
            data = get_roadmap_data(request.user)
            cache.set(cache_key, data, timeout=120)
        return Response(data)

    @action(detail=False, methods=["get"])
    def velocity(self, request):
        """Velocity por sprint + estimado vs tiempo real registrado."""
        from django.core.cache import cache

        from .advanced_metrics import get_velocity_data
        cache_key = f"velocity:{request.user.id}"
        data = cache.get(cache_key)
        if data is None:
            data = get_velocity_data(request.user)
            cache.set(cache_key, data, timeout=120)
        return Response(data)

    @action(detail=False, methods=["get"])
    def workload(self, request):
        """Workload Management: utilización por miembro (estimado vs capacidad)."""
        from django.core.cache import cache

        from .advanced_metrics import get_workload_data
        cache_key = f"workload:{request.user.id}"
        data = cache.get(cache_key)
        if data is None:
            data = get_workload_data(request.user)
            cache.set(cache_key, data, timeout=120)
        return Response(data)

    @action(detail=False, methods=["get"])
    def audit_dashboard(self, request):
        """Dashboard de auditoría con gráficos."""
        from django.core.cache import cache

        from .advanced_metrics import get_audit_dashboard
        cache_key = f"audit_dashboard:{request.user.id}"
        data = cache.get(cache_key)
        if data is None:
            data = get_audit_dashboard(request.user)
            cache.set(cache_key, data, timeout=60)
        return Response(data)

    @action(detail=False, methods=["post"])
    def bulk_delete(self, request):
        """Elimina múltiples tareas a la vez."""
        task_ids = request.data.get("task_ids", [])
        if not task_ids:
            return Response(
                {"error": "task_ids es requerido"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not isinstance(task_ids, list) or len(task_ids) > self.BULK_MAX_TASKS:
            return Response(
                {"error": f"Máximo {self.BULK_MAX_TASKS} tareas por operación"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        qs = Task.objects.for_user(request.user, write=True).filter(id__in=task_ids)
        count = qs.count()
        qs.delete()
        return Response({"deleted": count})

    @action(detail=False, methods=["post"])
    def bulk_move_sprint(self, request):
        """Mueve múltiples tareas a un sprint."""
        task_ids = request.data.get("task_ids", [])
        sprint_id = request.data.get("sprint_id")
        if not task_ids or not sprint_id:
            return Response(
                {"error": "task_ids y sprint_id son requeridos"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not isinstance(task_ids, list) or len(task_ids) > self.BULK_MAX_TASKS:
            return Response(
                {"error": f"Máximo {self.BULK_MAX_TASKS} tareas por operación"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # El sprint debe pertenecer a un proyecto editable por el usuario
        # (o ser propio sin proyecto)
        from django.db.models import Q

        from apps.projects.models import accessible_projects
        sprint = Sprint.objects.filter(
            Q(owner=request.user)
            | Q(project__in=accessible_projects(request.user, write=True)),
            id=sprint_id,
        ).first()
        if not sprint:
            return Response({"error": "Sprint no encontrado"}, status=status.HTTP_404_NOT_FOUND)
        qs = Task.objects.for_user(request.user, write=True).filter(id__in=task_ids)
        # Solo mover tareas del mismo proyecto que el sprint
        updated = qs.filter(project=sprint.project).update(sprint_id=sprint.id)
        return Response({"moved": updated})

    # --- Duplicado, recordatorios y productividad ---

    # Campos que NO se copian al duplicar: identidad, propiedad, jerarquía,
    # estado de cierre/recordatorio, recurrencia y metadatos de versionado.
    # El resto de campos escalares (título, descripción, proyecto, epic,
    # sprint, priority, task_type, size, fechas, estimaciones, assignee)
    # se copian tal cual.
    DUPLICATE_SKIP_FIELDS = {
        "id", "owner", "parent", "recurrence",
        "completed_at", "reminder_at", "reminder_sent",
        "created_at", "updated_at", "version",
    }

    def _duplicate_task(self, source, owner, parent=None):
        """Clona una tarea: escalares + tags + assignees + checklist +
        valores de campos personalizados.

        No copia comentarios, adjuntos, relaciones, entradas de tiempo,
        watchers ni la regla de recurrencia.
        """
        data = {
            f.name: getattr(source, f.name)
            for f in Task._meta.fields
            if f.name not in self.DUPLICATE_SKIP_FIELDS
        }
        # La copia nunca nace completada: vuelve a pendiente
        if data.get("state") == Task.State.COMPLETED:
            data["state"] = Task.State.PENDING
        clone = Task.objects.create(owner=owner, parent=parent, **data)
        clone.tags.set(source.tags.all())
        clone.assignees.set(source.assignees.all())
        # Checklist (Subtask) — conserva is_done y orden
        for sub in source.subtasks.all():
            Subtask.objects.create(
                task=clone, title=sub.title,
                is_done=sub.is_done, order=sub.order,
            )
        # Valores de campos personalizados (escalares JSON, sin enlaces)
        for cfv in source.custom_field_values.all():
            CustomFieldValue.objects.create(
                task=clone, field=cfv.field, value=cfv.value,
            )
        return clone

    @action(detail=True, methods=["post"])
    def duplicate(self, request, pk=None):
        """Duplica la tarea con tags, assignees y subtareas directas.

        Requiere acceso de escritura (get_object). Las subtareas hijas
        (parent) se clonan con nuevos ids colgando de la copia; el estado
        se preserva salvo completed→pending. No copia comentarios,
        adjuntos, relaciones, entradas de tiempo ni watchers.
        """
        from django.db import transaction
        task = self.get_object()
        with transaction.atomic():
            clone = self._duplicate_task(task, owner=request.user)
            for child in task.subtasks_children.all():
                self._duplicate_task(child, owner=request.user, parent=clone)
            TaskActivity.objects.create(
                task=clone, actor=request.user,
                action=TaskActivity.ActionType.CREATED,
                new_value=f"Duplicada de #{task.pk}",
            )
        serializer = TaskSerializer(
            clone, context=self.get_serializer_context()
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def snooze_reminder(self, request, pk=None):
        """Pospone el recordatorio N minutos (1..1440, por defecto 15).

        Body: {"minutes": int}. Resetea reminder_sent para que el beat
        send_due_reminders vuelva a notificar en la nueva fecha.
        """
        task = self.get_object()
        try:
            minutes = int(request.data.get("minutes", 15))
        except (TypeError, ValueError):
            minutes = 15
        minutes = min(max(minutes, 1), 1440)
        task.reminder_at = timezone.now() + timezone.timedelta(minutes=minutes)
        task.reminder_sent = False
        task.save(update_fields=["reminder_at", "reminder_sent"])
        return Response({"reminder_at": task.reminder_at.isoformat()})

    @action(detail=False, methods=["get"])
    def productivity(self, request):
        """Productividad diaria del usuario: tareas completadas por día.

        Cuenta las tareas visibles donde el usuario es owner o assignee
        (FK o M2M) con state=completed y completed_at dentro del rango
        ``days`` (1..365, por defecto 30). Devuelve la serie diaria con
        ceros, la racha de días consecutivos, el total, la media y el
        mejor día.
        """
        from django.db.models import Count, Q
        from django.db.models.functions import TruncDate
        try:
            days = min(max(int(request.query_params.get("days", 30)), 1), 365)
        except (TypeError, ValueError):
            days = 30
        today = timezone.localdate()
        start = today - timezone.timedelta(days=days - 1)
        rows = (
            Task.objects.for_user(request.user)
            # Limpiar el ordering por defecto (-created_at): con distinct()
            # Django lo mete en el GROUP BY y partiría un grupo por tarea
            .order_by()
            .filter(
                Q(owner=request.user)
                | Q(assignee=request.user)
                | Q(assignees=request.user),
                state=Task.State.COMPLETED,
                completed_at__isnull=False,
                completed_at__date__gte=start,
                completed_at__date__lte=today,
            )
            .annotate(day=TruncDate("completed_at"))
            .values("day")
            # distinct=True: for_user hace joins (memberships, assignees)
            # que duplicarían filas en el GROUP BY sin el distinct
            .annotate(n=Count("id", distinct=True))
        )
        counts = {row["day"]: row["n"] for row in rows}
        daily = [
            {
                "date": (start + timezone.timedelta(days=i)).isoformat(),
                "count": counts.get(start + timezone.timedelta(days=i), 0),
            }
            for i in range(days)
        ]
        total = sum(counts.values())
        # Racha: hacia atrás desde hoy si hoy tiene ≥1; si no, desde ayer
        streak = 0
        cursor = (
            today if counts.get(today, 0) > 0
            else today - timezone.timedelta(days=1)
        )
        while counts.get(cursor, 0) > 0:
            streak += 1
            cursor -= timezone.timedelta(days=1)
        return Response({
            "daily": daily,
            "streak": streak,
            "total": total,
            "avg_per_day": round(total / days, 1),
            "best_day": max(counts.values(), default=0),
        })


class SubtaskViewSet(viewsets.ModelViewSet):
    serializer_class = SubtaskSerializer

    def get_queryset(self):
        tasks = Task.objects.for_user(self.request.user)
        return Subtask.objects.filter(task__in=tasks)

    def get_object(self):
        obj = super().get_object()
        if self.request.method in ("PUT", "PATCH", "DELETE") and not Task.objects.for_user(
            self.request.user, write=True
        ).filter(pk=obj.task_id).exists():
            raise PermissionDenied(
                "Tienes acceso de solo lectura a esta tarea"
            )
        return obj


class CommentViewSet(viewsets.ModelViewSet):
    serializer_class = CommentSerializer

    def get_queryset(self):
        from django.db.models import Count
        tasks = Task.objects.for_user(self.request.user)
        return Comment.objects.filter(task__in=tasks).select_related(
            "author"
        ).annotate(replies_count_ann=Count("replies", distinct=True))

    def get_object(self):
        obj = super().get_object()
        if self.request.method in ("PUT", "PATCH", "DELETE"):
            # Editar/borrar: el autor, o quien tenga permiso de escritura en la tarea
            editable = Task.objects.for_user(
                self.request.user, write=True
            ).filter(pk=obj.task_id).exists()
            if obj.author_id != self.request.user.id and not editable:
                raise PermissionDenied(
                    "Solo el autor o un editor del proyecto puede modificar el comentario"
                )
        return obj

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @action(detail=True, methods=["post"])
    def react(self, request, pk=None):
        """Añade/quita una reacción emoji del usuario al comentario.

        Body: {"emoji": "👍"} — toggle: si ya la tiene la quita, si no la
        añade. Las reacciones se guardan como {"emoji": [user_ids]}.
        """
        comment = self.get_object()
        emoji = request.data.get("emoji", "")
        if not emoji or len(emoji) > 8:
            return Response(
                {"error": "emoji requerido (máx 8 chars)"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        reactions = dict(comment.reactions or {})
        users = reactions.get(emoji, [])
        if request.user.id in users:
            users.remove(request.user.id)
            if not users:
                reactions.pop(emoji)
        else:
            users.append(request.user.id)
            reactions[emoji] = users
        comment.reactions = reactions
        comment.save(update_fields=["reactions"])
        return Response(CommentSerializer(comment).data)


class SprintViewSet(viewsets.ModelViewSet):
    """CRUD de sprints."""
    serializer_class = SprintSerializer
    filterset_fields = ["state", "project"]
    ordering_fields = ["start_date", "end_date", "created_at"]

    def get_queryset(self):
        # Lectura: sprints propios o de proyectos compartidos.
        # Escritura: solo proyectos editables.
        write = self.action in (
            "create", "update", "partial_update", "destroy", "close",
        )
        from django.db.models import Count, Q

        from apps.projects.models import accessible_projects
        if write:
            return Sprint.objects.filter(
                Q(owner=self.request.user)
                | Q(project__in=accessible_projects(self.request.user, write=True))
            ).select_related("project")
        return Sprint.objects.filter(
            Q(owner=self.request.user)
            | Q(project__in=accessible_projects(self.request.user))
        ).select_related("project").annotate(
            task_count_ann=Count("tasks", distinct=True)
        ).order_by(*Sprint._meta.ordering)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=["get"])
    def tasks(self, request, pk=None):
        sprint = self.get_object()
        tasks = Task.objects.for_user(request.user).filter(sprint=sprint)
        serializer = TaskSerializer(tasks, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        """Cierra el sprint activo (rollover estilo Jira).

        Body opcional ``move_incomplete_to``:
          - ``<sprint_id:int>`` → mueve las tareas no terminales
            (state ∉ completed/cancelled/archived) a ese sprint;
          - ``"backlog"`` → las mueve al backlog (sprint=None);
          - omitido/null → solo cierra el sprint.
        ``next_sprint_id`` se mantiene por compatibilidad (equivale a
        pasar el id en ``move_incomplete_to``).
        El sprint destino debe ser del mismo proyecto y distinto del
        que se cierra. La respuesta incluye ``moved_incomplete``.
        """
        from django.db import transaction
        sprint = self.get_object()
        if sprint.state != Sprint.SprintState.ACTIVE:
            return Response(
                {"error": "Solo se pueden cerrar sprints activos"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        move_to = request.data.get("move_incomplete_to")
        # Compat: next_sprint_id legacy equivale a un id destino
        if move_to in (None, ""):
            move_to = request.data.get("next_sprint_id")
        target_sprint = None
        move_to_backlog = False
        if move_to == "backlog":
            move_to_backlog = True
        elif move_to not in (None, ""):
            try:
                target_id = int(move_to)
            except (TypeError, ValueError):
                return Response(
                    {"error": "move_incomplete_to debe ser un id de sprint o 'backlog'"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if target_id == sprint.id:
                return Response(
                    {"error": "El sprint destino no puede ser el sprint que se cierra"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            target_sprint = Sprint.objects.filter(id=target_id).first()
            if target_sprint is None:
                return Response(
                    {"error": "Siguiente sprint no encontrado"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            # Coherencia: mismo proyecto que el sprint de origen
            if target_sprint.project_id != sprint.project_id:
                return Response(
                    {"error": "El sprint destino debe ser del mismo proyecto"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        moved = 0
        with transaction.atomic():
            incomplete = sprint.tasks.exclude(
                state__in=[
                    Task.State.COMPLETED,
                    Task.State.CANCELLED,
                    Task.State.ARCHIVED,
                ]
            )
            if move_to_backlog or target_sprint is not None:
                new_sprint = None if move_to_backlog else target_sprint
                for t in incomplete:
                    t.sprint = new_sprint
                    t.save(update_fields=["sprint"])
                    moved += 1
            sprint.state = Sprint.SprintState.CLOSED
            sprint.save(update_fields=["state"])
        return Response({
            "message": f"Sprint cerrado. {moved} tareas movidas al siguiente sprint.",
            "moved_incomplete": moved,
        })

    @action(detail=False, methods=["get"])
    def active(self, request):
        from django.db.models import Q

        from apps.projects.models import accessible_projects
        sprint = Sprint.objects.filter(
            Q(owner=request.user)
            | Q(project__in=accessible_projects(request.user)),
            state=Sprint.SprintState.ACTIVE,
        ).first()
        if not sprint:
            return Response(None)
        serializer = self.get_serializer(sprint)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def metrics(self, request, pk=None):
        """Métricas de un sprint específico."""
        result = get_sprint_metrics(request.user, pk)
        if result is None:
            return Response(
                {"error": "Sprint no encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(result)


class EpicViewSet(viewsets.ModelViewSet):
    """CRUD de épicas."""
    serializer_class = EpicSerializer
    filterset_fields = ["state", "project"]
    ordering_fields = ["created_at", "start_date", "end_date"]

    def get_queryset(self):
        from django.db.models import Count, Q

        from apps.projects.models import accessible_projects
        write = self.action in ("create", "update", "partial_update", "destroy")
        projects = accessible_projects(self.request.user, write=write)
        return Epic.objects.filter(
            Q(owner=self.request.user) | Q(project__in=projects)
        ).select_related("project").annotate(
            progress_total_ann=Count("tasks", distinct=True),
            progress_done_ann=Count(
                "tasks", filter=Q(tasks__state="completed"), distinct=True
            ),
        ).order_by(*Epic._meta.ordering)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=["get"])
    def tasks(self, request, pk=None):
        epic = self.get_object()
        tasks = Task.objects.for_user(request.user).filter(epic=epic)
        serializer = TaskSerializer(tasks, many=True)
        return Response(serializer.data)


class SavedSearchViewSet(viewsets.ModelViewSet):
    """CRUD de búsquedas guardadas."""
    serializer_class = SavedSearchSerializer

    def get_queryset(self):
        qs = SavedSearch.objects.filter(owner=self.request.user)
        # Incluir búsquedas compartidas de otros usuarios (solo lectura)
        shared = SavedSearch.objects.filter(is_shared=True).exclude(owner=self.request.user)
        return (qs | shared).distinct()

    def check_object_permissions(self, request, obj):
        super().check_object_permissions(request, obj)
        # Las búsquedas compartidas de otros usuarios son read-only
        if request.method not in ("GET", "HEAD", "OPTIONS") and obj.owner_id != request.user.id:
            self.permission_denied(
                request, message="Solo el propietario puede modificar esta búsqueda"
            )

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class TaskRelationViewSet(viewsets.ModelViewSet):
    """CRUD de relaciones entre tareas."""
    serializer_class = TaskRelationSerializer

    def get_queryset(self):
        # Relaciones cuyo source es una tarea accesible (propia o compartida)
        tasks = Task.objects.for_user(self.request.user)
        return TaskRelation.objects.filter(
            source__in=tasks
        ).select_related("source", "target")

    def get_object(self):
        obj = super().get_object()
        if self.request.method in ("PUT", "PATCH", "DELETE") and not Task.objects.for_user(
            self.request.user, write=True
        ).filter(pk=obj.source_id).exists():
            raise PermissionDenied(
                "Tienes acceso de solo lectura a esta relación"
            )
        return obj


class TimeEntryViewSet(viewsets.ModelViewSet):
    """CRUD de registros de tiempo."""
    serializer_class = TimeEntrySerializer
    filterset_fields = ["task", "user"]
    ordering_fields = ["created_at", "started_at"]

    def get_queryset(self):
        return TimeEntry.objects.filter(
            user=self.request.user
        ).select_related("task", "user")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class AttachmentViewSet(viewsets.ModelViewSet):
    """CRUD de adjuntos."""
    serializer_class = AttachmentSerializer
    filterset_fields = ["task", "comment"]

    def get_queryset(self):
        # Adjuntos de tareas accesibles (propias o proyectos compartidos)
        # o subidos por el usuario
        tasks = Task.objects.for_user(self.request.user)
        return (
            Attachment.objects.filter(task__in=tasks)
            | Attachment.objects.filter(uploaded_by=self.request.user)
        ).select_related("task", "comment").distinct()

    def get_object(self):
        obj = super().get_object()
        if self.request.method in ("PUT", "PATCH", "DELETE"):
            editable = Task.objects.for_user(
                self.request.user, write=True
            ).filter(pk=obj.task_id).exists()
            if obj.uploaded_by_id != self.request.user.id and not editable:
                raise PermissionDenied(
                    "Solo el autor o un editor del proyecto puede modificar el adjunto"
                )
        return obj

    # Magic bytes de los tipos permitidos (el Content-Type del cliente es falseable)
    _MAGIC = {
        "image/jpeg": (b"\xff\xd8\xff",),
        "image/png": (b"\x89PNG\r\n\x1a\n",),
        "image/gif": (b"GIF87a", b"GIF89a"),
        "image/webp": (b"RIFF",),  # + WEBP en offset 8 (verificado aparte)
        "application/pdf": (b"%PDF",),
        "application/zip": (b"PK\x03\x04", b"PK\x05\x06"),
        "application/x-zip-compressed": (b"PK\x03\x04", b"PK\x05\x06"),
    }
    _MAGIC.update({
        # OOXML son contenedores ZIP
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            (b"PK\x03\x04",),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
            (b"PK\x03\x04",),
        "application/msword": (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",),
        "application/vnd.ms-excel": (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", b"PK\x03\x04"),
    })
    # Tipos de texto sin firma binaria fiable: solo validan extensión
    _TEXT_TYPES = {"text/plain", "text/csv"}
    _ALLOWED_TYPES = set(_MAGIC) | _TEXT_TYPES
    _BLOCKED_EXT = {
        ".exe", ".dll", ".bat", ".cmd", ".ps1", ".sh", ".msi", ".com",
        ".scr", ".vbs", ".js", ".jar", ".hta", ".html", ".htm", ".svg",
    }

    @classmethod
    def _sniff_ok(cls, file, declared: str) -> bool:
        """Verifica magic bytes cuando el tipo declarado tiene firma conocida."""
        if declared in cls._TEXT_TYPES:
            return True  # sin firma binaria fiable
        head = file.read(16)
        file.seek(0)
        sigs = cls._MAGIC.get(declared)
        if not sigs:
            return False
        if declared == "image/webp":
            return head[:4] == b"RIFF" and head[8:12] == b"WEBP"
        return any(head.startswith(s) for s in sigs)

    def perform_create(self, serializer):
        import os as _os

        from django.utils.text import get_valid_filename
        from rest_framework.exceptions import ValidationError

        file = self.request.FILES.get("file")
        external_url = self.request.data.get("external_url", "").strip()
        if not file and external_url:
            # Adjunto como enlace externo (Drive, Dropbox...): sin fichero,
            # el nombre viene del payload y no aplica sniffing de magic bytes.
            name = get_valid_filename(
                self.request.data.get("filename") or external_url
            )[:255]
            serializer.save(
                uploaded_by=self.request.user,
                external_url=external_url,
                filename=name,
            )
            return
        file_size = file.size if file else 0
        content_type = file.content_type if file else ""
        filename = file.name if file else ""

        max_size = getattr(settings, "ATTACHMENT_MAX_SIZE", 10 * 1024 * 1024)
        if file_size > max_size:
            raise ValidationError(
                {"file": f"El archivo excede el tamaño máximo de {max_size // (1024 * 1024)}MB"}
            )

        # Sanitización del nombre: elimina path traversal y caracteres de control
        filename = get_valid_filename(_os.path.basename(filename or "file"))
        ext = _os.path.splitext(filename)[1].lower()
        if ext in self._BLOCKED_EXT:
            raise ValidationError({"file": f"Extensión no permitida: {ext}"})

        if content_type and content_type not in self._ALLOWED_TYPES:
            raise ValidationError({"file": f"Tipo de archivo no permitido: {content_type}"})

        # Sniffing real: el Content-Type declarado debe coincidir con la firma
        if file and content_type and not self._sniff_ok(file, content_type):
            raise ValidationError(
                {"file": "El contenido del archivo no coincide con su tipo declarado"}
            )

        serializer.save(
            uploaded_by=self.request.user,
            file_size=file_size,
            content_type=content_type,
            filename=filename,
        )

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        """Descarga un adjunto con autorización."""
        attachment = self.get_object()
        if not attachment.file:
            return Response(
                {"error": "Archivo no disponible"},
                status=status.HTTP_404_NOT_FOUND,
            )
        from django.http import FileResponse
        response = FileResponse(
            attachment.file.open("rb"),
            as_attachment=True,
            filename=attachment.filename or os.path.basename(attachment.file.name),
        )
        response["Content-Type"] = attachment.content_type or "application/octet-stream"
        return response


class TaskTemplateViewSet(viewsets.ModelViewSet):
    """CRUD de plantillas de tareas."""
    serializer_class = TaskTemplateSerializer
    filterset_fields = ["project"]
    ordering_fields = ["created_at"]

    def get_queryset(self):
        return TaskTemplate.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=["post"])
    def create_task(self, request, pk=None):
        """Crea una tarea a partir de la plantilla."""
        template = self.get_object()
        overrides = request.data.get("overrides", {})
        task = template.create_task(request.user, overrides)
        return Response(TaskSerializer(task).data, status=status.HTTP_201_CREATED)


class CustomFieldViewSet(viewsets.ModelViewSet):
    """CRUD de campos personalizados."""
    serializer_class = CustomFieldSerializer
    filterset_fields = ["project"]

    def get_queryset(self):
        from apps.projects.models import accessible_projects
        write = self.action in ("create", "update", "partial_update", "destroy")
        return CustomField.objects.filter(
            project__in=accessible_projects(self.request.user, write=write)
        ).select_related("project")

    def perform_create(self, serializer):
        serializer.save()


class CustomFieldValueViewSet(viewsets.ModelViewSet):
    """CRUD de valores de campos personalizados."""
    serializer_class = CustomFieldValueSerializer
    filterset_fields = ["task", "field"]

    def get_queryset(self):
        write = self.action in ("create", "update", "partial_update", "destroy")
        tasks = Task.objects.for_user(self.request.user, write=write)
        return CustomFieldValue.objects.filter(
            task__in=tasks
        ).select_related("task", "field")


class OutgoingWebhookViewSet(viewsets.ModelViewSet):
    """CRUD de webhooks salientes."""
    serializer_class = OutgoingWebhookSerializer

    def get_queryset(self):
        return OutgoingWebhook.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=["post"])
    def test(self, request, pk=None):
        """Envía un payload de test al webhook."""
        import requests

        webhook = self.get_object()

        # Validación SSRF completa: scheme + resolución DNS + IPs internas
        from apps.integrations_chat.services import _is_safe_url
        if not _is_safe_url(webhook.url):
            return Response(
                {"error": "URL no permitida"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payload = {
            "event": "test",
            "message": "Test webhook from TODOlist",
            "timestamp": timezone.now().isoformat(),
        }
        try:
            resp = requests.post(
                webhook.url,
                json=payload,
                timeout=10,
                headers={"Content-Type": "application/json"},
                allow_redirects=False,
            )
            return Response({
                "status_code": resp.status_code,
                "response": resp.text[:500],
            })
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                "Error enviando webhook de test %s", webhook.id
            )
            return Response(
                {"error": "Error de conexión con el webhook"},
                status=status.HTTP_502_BAD_GATEWAY,
            )


class RecurrenceRuleViewSet(viewsets.ModelViewSet):
    """CRUD de reglas de recurrencia para tareas repetitivas."""
    serializer_class = RecurrenceRuleSerializer

    def get_queryset(self):
        return RecurrenceRule.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)
