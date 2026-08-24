from django.conf import settings
from django.db import models
from django.utils import timezone
from datetime import timedelta

from apps.projects.models import Project
from apps.tags.models import Tag


class TaskQuerySet(models.QuerySet):
    def for_user(self, user):
        return self.filter(owner=user)


class RecurrenceRule(models.Model):
    """Regla de recurrencia para una tarea recurrente."""

    class Frequency(models.TextChoices):
        DAILY = "daily", "Diaria"
        WEEKLY = "weekly", "Semanal"
        MONTHLY = "monthly", "Mensual"
        YEARLY = "yearly", "Anual"

    frequency = models.CharField(
        max_length=10, choices=Frequency.choices, default=Frequency.DAILY
    )
    interval = models.PositiveIntegerField(default=1)
    until = models.DateTimeField(null=True, blank=True)
    count = models.PositiveIntegerField(null=True, blank=True)
    occurrences_generated = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Cada {self.interval} {self.frequency}"

    def next_due_date(self, from_date=None):
        base = from_date or timezone.now()
        if self.frequency == self.Frequency.DAILY:
            return base + timedelta(days=self.interval)
        elif self.frequency == self.Frequency.WEEKLY:
            return base + timedelta(weeks=self.interval)
        elif self.frequency == self.Frequency.MONTHLY:
            return base + timedelta(days=30 * self.interval)
        elif self.frequency == self.Frequency.YEARLY:
            return base + timedelta(days=365 * self.interval)
        return None

    def should_continue(self):
        """Determina si la regla debe seguir generando ocurrencias.
        Se llama DESPUÉS de incrementar occurrences_generated.
        """
        if self.until and timezone.now() > self.until:
            return False
        if self.count and self.occurrences_generated >= self.count:
            return False
        return True


class Task(models.Model):
    """Tarea perteneciente a un proyecto (o bandeja de entrada si project=None)."""

    class State(models.TextChoices):
        BACKLOG = "backlog", "Backlog"
        PENDING = "pending", "Pendiente"
        IN_PROGRESS = "in_progress", "En progreso"
        BLOCKED = "blocked", "Bloqueada"
        REVIEW = "review", "En revision"
        COMPLETED = "completed", "Completada"
        CANCELLED = "cancelled", "Cancelada"
        ARCHIVED = "archived", "Archivada"

    class Priority(models.IntegerChoices):
        P0_CRITICAL = 0, "P0 Critica"
        P1_VERY_HIGH = 1, "P1 Muy alta"
        P2_HIGH = 2, "P2 Alta"
        P3_MEDIUM = 3, "P3 Media"
        P4_LOW = 4, "P4 Baja"
        P5_SOMEDAY = 5, "P5 Algun dia"

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
    recurrence = models.ForeignKey(
        RecurrenceRule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tasks",
    )

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

    def generate_next_occurrence(self):
        """Genera la siguiente instancia de una tarea recurrente."""
        if not self.recurrence:
            return None
        # Incrementar primero y luego evaluar si debe seguir
        self.recurrence.occurrences_generated += 1
        if not self.recurrence.should_continue():
            self.recurrence.occurrences_generated -= 1
            self.recurrence.save(update_fields=["occurrences_generated"])
            return None

        next_due = self.recurrence.next_due_date(self.due_date or timezone.now())

        new_task = Task.objects.create(
            owner=self.owner,
            project=self.project,
            title=self.title,
            description=self.description,
            state=Task.State.PENDING,
            priority=self.priority,
            due_date=next_due,
            recurrence=self.recurrence,
        )
        if self.tags.exists():
            new_task.tags.set(self.tags.all())

        self.recurrence.save(update_fields=["occurrences_generated"])

        return new_task


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
