from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Task, Subtask, Comment, TaskRelation, TaskActivity, Sprint, Epic, SavedSearch
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
        )
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
        instance = serializer.save()
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
