from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import (
    Task, Subtask, Comment, TaskRelation, TaskActivity, Sprint, Epic,
    SavedSearch, TimeEntry, Attachment, TaskTemplate, CustomField,
    CustomFieldValue, OutgoingWebhook,
)
from .serializers import (
    TaskSerializer,
    TaskCreateUpdateSerializer,
    SubtaskSerializer,
    CommentSerializer,
    TaskRelationSerializer,
    TaskActivitySerializer,
    SprintSerializer,
    EpicSerializer,
    SavedSearchSerializer,
    TimeEntrySerializer,
    AttachmentSerializer,
    TaskTemplateSerializer,
    CustomFieldSerializer,
    CustomFieldValueSerializer,
    OutgoingWebhookSerializer,
    SavedSearchSerializer,
)
from .metrics import (
    get_flow_metrics, get_backlog_health, get_sprint_metrics,
    get_dashboard_summary, get_pr_metrics,
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
        "sprint", "epic", "parent",
    ]
    search_fields = ["title", "description"]
    ordering_fields = [
        "created_at", "updated_at", "due_date", "priority", "title",
        "start_date", "story_points",
    ]

    def get_queryset(self):
        qs = Task.objects.for_user(self.request.user).select_related(
            "project", "sprint", "epic", "parent"
        ).prefetch_related("tags", "subtasks")
        due_before = self.request.query_params.get("due_before")
        due_after = self.request.query_params.get("due_after")
        if due_before:
            qs = qs.filter(due_date__date__lte=due_before)
        if due_after:
            qs = qs.filter(due_date__date__gte=due_after)
        # Filtro por sprint activo
        active_sprint = self.request.query_params.get("active_sprint")
        if active_sprint == "true":
            qs = qs.filter(sprint__state=Sprint.SprintState.ACTIVE)
        # Filtro por épica
        epic_id = self.request.query_params.get("epic_id")
        if epic_id:
            qs = qs.filter(epic_id=epic_id)
        return qs

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return TaskCreateUpdateSerializer
        return TaskSerializer

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def perform_update(self, serializer):
        old_state = serializer.instance.state
        instance = serializer.save()
        # Registrar cambio de estado
        if old_state != instance.state:
            TaskActivity.objects.create(
                task=instance,
                actor=self.request.user,
                action=TaskActivity.ActionType.STATE_CHANGED,
                old_value=old_state,
                new_value=instance.state,
            )
        if instance.state == Task.State.COMPLETED and not instance.completed_at:
            instance.completed_at = timezone.now()
            instance.save(update_fields=["completed_at"])
            if instance.recurrence:
                instance.generate_next_occurrence()
        elif instance.state != Task.State.COMPLETED and instance.completed_at:
            instance.completed_at = None
            instance.save(update_fields=["completed_at"])

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
        serializer = CommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(task=task, author=request.user)
        TaskActivity.objects.create(
            task=task, actor=request.user,
            action=TaskActivity.ActionType.COMMENTED,
            new_value=serializer.data["body"][:200],
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

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
        # POST: crear relación
        serializer = TaskRelationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target_id = serializer.validated_data["target"].id
        # Verificar que target pertenece al usuario
        if not Task.objects.filter(id=target_id, owner=request.user).exists():
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
            sprint = Sprint.objects.get(id=sprint_id, owner=request.user)
        except Sprint.DoesNotExist:
            return Response(
                {"error": "Sprint no encontrado"},
                status=status.HTTP_404_NOT_FOUND,
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
        days = int(request.query_params.get("days", 30))
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
        qs = Task.objects.for_user(request.user).filter(id__in=task_ids)
        updated = qs.update(**updates)
        return Response({"updated": updated})

    @action(detail=False, methods=["get"])
    def search(self, request):
        """Búsqueda full-text sobre tareas."""
        from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
        from django.db.models import Q

        query = request.query_params.get("q", "").strip()
        if not query:
            return Response({"results": [], "count": 0})

        qs = Task.objects.for_user(request.user)
        # Búsqueda simple con Q (compatible con SQLite en tests)
        qs = qs.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query)
        ).select_related("project", "sprint").prefetch_related("tags")[:50]

        serializer = self.get_serializer(qs, many=True)
        return Response({"results": serializer.data, "count": len(serializer.data)})

    @action(detail=False, methods=["get"])
    def gantt(self, request):
        """Datos para vista Gantt."""
        from .advanced_metrics import get_gantt_data
        from django.core.cache import cache
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

    @action(detail=False, methods=["get"])
    def capacity(self, request):
        """Datos de capacity planning."""
        from .advanced_metrics import get_capacity_data
        from django.core.cache import cache
        cache_key = f"capacity:{request.user.id}"
        data = cache.get(cache_key)
        if data is None:
            data = get_capacity_data(request.user)
            cache.set(cache_key, data, timeout=120)
        return Response(data)

    @action(detail=False, methods=["get"])
    def audit_dashboard(self, request):
        """Dashboard de auditoría con gráficos."""
        from .advanced_metrics import get_audit_dashboard
        from django.core.cache import cache
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
        qs = Task.objects.for_user(request.user).filter(id__in=task_ids)
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
        qs = Task.objects.for_user(request.user).filter(id__in=task_ids)
        updated = qs.update(sprint_id=sprint_id)
        return Response({"moved": updated})


class SubtaskViewSet(viewsets.ModelViewSet):
    serializer_class = SubtaskSerializer

    def get_queryset(self):
        return Subtask.objects.filter(task__owner=self.request.user)


class CommentViewSet(viewsets.ModelViewSet):
    serializer_class = CommentSerializer

    def get_queryset(self):
        return Comment.objects.filter(task__owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)


class SprintViewSet(viewsets.ModelViewSet):
    """CRUD de sprints."""
    serializer_class = SprintSerializer
    filterset_fields = ["state", "project"]
    ordering_fields = ["start_date", "end_date", "created_at"]

    def get_queryset(self):
        return Sprint.objects.filter(owner=self.request.user).select_related("project")

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=["get"])
    def tasks(self, request, pk=None):
        sprint = self.get_object()
        tasks = Task.objects.filter(owner=request.user, sprint=sprint)
        serializer = TaskSerializer(tasks, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        sprint = self.get_object()
        if sprint.state != Sprint.SprintState.ACTIVE:
            return Response(
                {"error": "Solo se pueden cerrar sprints activos"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Mover tareas no completadas al siguiente sprint si se especifica
        next_sprint_id = request.data.get("next_sprint_id")
        incomplete = sprint.tasks.exclude(
            state__in=[Task.State.COMPLETED, Task.State.CANCELLED]
        )
        moved = 0
        if next_sprint_id:
            try:
                next_sprint = Sprint.objects.get(id=next_sprint_id, owner=request.user)
                for t in incomplete:
                    t.sprint = next_sprint
                    t.save(update_fields=["sprint"])
                    moved += 1
            except Sprint.DoesNotExist:
                return Response(
                    {"error": "Siguiente sprint no encontrado"},
                    status=status.HTTP_404_NOT_FOUND,
                )
        sprint.state = Sprint.SprintState.CLOSED
        sprint.save(update_fields=["state"])
        return Response({
            "message": f"Sprint cerrado. {moved} tareas movidas al siguiente sprint.",
        })

    @action(detail=False, methods=["get"])
    def active(self, request):
        sprint = Sprint.objects.filter(
            owner=request.user, state=Sprint.SprintState.ACTIVE
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
        return Epic.objects.filter(owner=self.request.user).select_related("project")

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=["get"])
    def tasks(self, request, pk=None):
        epic = self.get_object()
        tasks = Task.objects.filter(owner=request.user, epic=epic)
        serializer = TaskSerializer(tasks, many=True)
        return Response(serializer.data)


class SavedSearchViewSet(viewsets.ModelViewSet):
    """CRUD de búsquedas guardadas."""
    serializer_class = SavedSearchSerializer

    def get_queryset(self):
        qs = SavedSearch.objects.filter(owner=self.request.user)
        # Incluir búsquedas compartidas de otros usuarios
        shared = SavedSearch.objects.filter(is_shared=True).exclude(owner=self.request.user)
        return (qs | shared).distinct()

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class TaskRelationViewSet(viewsets.ModelViewSet):
    """CRUD de relaciones entre tareas."""
    serializer_class = TaskRelationSerializer

    def get_queryset(self):
        return TaskRelation.objects.filter(
            source__owner=self.request.user
        ).select_related("source", "target")


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
        return Attachment.objects.filter(
            uploaded_by=self.request.user
        ).select_related("task", "comment")

    def perform_create(self, serializer):
        import os
        file = self.request.FILES.get("file")
        file_size = file.size if file else 0
        content_type = file.content_type if file else ""
        filename = file.name if file else ""
        serializer.save(
            uploaded_by=self.request.user,
            file_size=file_size,
            content_type=content_type,
            filename=filename,
        )


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
        return CustomField.objects.filter(
            project__owner=self.request.user
        ).select_related("project")

    def perform_create(self, serializer):
        serializer.save()


class CustomFieldValueViewSet(viewsets.ModelViewSet):
    """CRUD de valores de campos personalizados."""
    serializer_class = CustomFieldValueSerializer
    filterset_fields = ["task", "field"]

    def get_queryset(self):
        return CustomFieldValue.objects.filter(
            task__owner=self.request.user
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
        import json
        import requests
        webhook = self.get_object()
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
            )
            return Response({
                "status_code": resp.status_code,
                "response": resp.text[:500],
            })
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_502_BAD_GATEWAY,
            )
