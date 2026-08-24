from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Task, Subtask, Comment
from .serializers import (
    TaskSerializer,
    TaskCreateUpdateSerializer,
    SubtaskSerializer,
    CommentSerializer,
)


class TaskCreateUpdateViewSetMixin:
    """Devuelve la representación completa tras create/update."""

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        # Devolver con TaskSerializer (incluye recurrence, subtasks, etc.)
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
    """CRUD de tareas con filtros por estado, prioridad, etiqueta, proyecto y fecha."""

    filterset_fields = ["state", "priority", "project", "tags"]
    search_fields = ["title", "description"]
    ordering_fields = [
        "created_at", "updated_at", "due_date", "priority", "title",
    ]

    def get_queryset(self):
        qs = Task.objects.for_user(self.request.user).select_related("project")
        # Filtro por fecha de vencimiento (antes de / después de)
        due_before = self.request.query_params.get("due_before")
        due_after = self.request.query_params.get("due_after")
        if due_before:
            qs = qs.filter(due_date__date__lte=due_before)
        if due_after:
            qs = qs.filter(due_date__date__gte=due_after)
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
            # Si la tarea es recurrente, generar la siguiente ocurrencia
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
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def comments(self, request, pk=None):
        task = self.get_object()
        serializer = CommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(task=task, author=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class SubtaskViewSet(viewsets.ModelViewSet):
    serializer_class = SubtaskSerializer

    def get_queryset(self):
        return Subtask.objects.filter(task__owner=self.request.user)


class CommentViewSet(viewsets.ModelViewSet):
    serializer_class = CommentSerializer

    def get_queryset(self):
        return Comment.objects.filter(task__owner=self.request.user)

    def perform_create(self, serializer):
        # El autor se asigna desde una acción dedicada en TaskViewSet,
        # pero por seguridad también lo fijamos aquí si se usa directamente.
        serializer.save(author=self.request.user)
