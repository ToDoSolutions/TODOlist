from django.conf import settings
from django.db import models

from apps.projects.models import Project
from apps.tags.models import Tag


class TaskQuerySet(models.QuerySet):
    def for_user(self, user):
        return self.filter(owner=user)


class Task(models.Model):
    """Tarea perteneciente a un proyecto (o bandeja de entrada si project=None)."""

    class State(models.TextChoices):
        BACKLOG = "backlog", "Backlog"
        PENDING = "pending", "Pendiente"
        IN_PROGRESS = "in_progress", "En progreso"
        BLOCKED = "blocked", "Bloqueada"
        REVIEW = "review", "En revisión"
        COMPLETED = "completed", "Completada"
        CANCELLED = "cancelled", "Cancelada"
        ARCHIVED = "archived", "Archivada"

    class Priority(models.IntegerChoices):
        P0_CRITICAL = 0, "P0 Crítica"
        P1_VERY_HIGH = 1, "P1 Muy alta"
        P2_HIGH = 2, "P2 Alta"
        P3_MEDIUM = 3, "P3 Media"
        P4_LOW = 4, "P4 Baja"
        P5_SOMEDAY = 5, "P5 Algún día"

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    state = models.CharField(
        max_length=16, choices=State.choices, default=State.PENDING
    )
    priority = models.IntegerField(
        choices=Priority.choices, default=Priority.P3_MEDIUM
    )
    due_date = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="tasks",
        null=True,
        blank=True,
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name="tasks")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TaskQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["state"]),
            models.Index(fields=["priority"]),
            models.Index(fields=["due_date"]),
        ]

    def __str__(self) -> str:
        return self.title


class Subtask(models.Model):
    """Subtarea / checklist dentro de una tarea."""

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="subtasks")
    title = models.CharField(max_length=255)
    is_done = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self) -> str:
        return self.title


class Comment(models.Model):
    """Comentario en una tarea."""

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Comentario en {self.task_id} por {self.author_id}"
