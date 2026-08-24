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

    class Type(models.TextChoices):
        BUG = "bug", "Bug"
        FEATURE = "feature", "Funcionalidad"
        IMPROVEMENT = "improvement", "Mejora"
        TASK = "task", "Tarea"
        RESEARCH = "research", "Investigacion"
        TECH_DEBT = "tech_debt", "Deuda tecnica"
        DOCS = "docs", "Documentacion"
        OPS = "ops", "Incidencia operativa"

    class Size(models.TextChoices):
        XS = "xs", "XS"
        S = "s", "S"
        M = "m", "M"
        L = "l", "L"
        XL = "xl", "XL"

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    state = models.CharField(
        max_length=16, choices=State.choices, default=State.PENDING
    )
    priority = models.IntegerField(
        choices=Priority.choices, default=Priority.P3_MEDIUM
    )
    task_type = models.CharField(
        max_length=20, choices=Type.choices, default=Type.TASK
    )
    due_date = models.DateTimeField(null=True, blank=True)
    start_date = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Estimacion
    story_points = models.PositiveIntegerField(null=True, blank=True)
    estimate_hours = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    size = models.CharField(
        max_length=3, choices=Size.choices, blank=True, default=""
    )

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

    # Jerarquia: parent para sub-issues
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="subtasks_children",
        null=True,
        blank=True,
    )
    # Sprint asignado
    sprint = models.ForeignKey(
        "Sprint",
        on_delete=models.SET_NULL,
        related_name="tasks",
        null=True,
        blank=True,
    )
    # Epica asignada
    epic = models.ForeignKey(
        "Epic",
        on_delete=models.SET_NULL,
        related_name="tasks",
        null=True,
        blank=True,
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
            models.Index(fields=["task_type"]),
            models.Index(fields=["sprint"]),
            models.Index(fields=["epic"]),
            models.Index(fields=["parent"]),
        ]

    def __str__(self) -> str:
        return self.title

    def generate_next_occurrence(self):
        """Genera la siguiente instancia de una tarea recurrente."""
        if not self.recurrence:
            return None
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

    @property
    def subtask_progress(self):
        """Progreso de subtareas: (completadas, total)."""
        children = self.subtasks_children.all()
        total = children.count()
        if total == 0:
            return (0, 0)
        done = children.filter(state__in=[Task.State.COMPLETED, Task.State.CANCELLED]).count()
        return (done, total)


class TaskRelation(models.Model):
    """Relacion entre dos tareas (bloquea, relacionada, duplica, etc)."""

    class RelationType(models.TextChoices):
        BLOCKS = "blocks", "Bloquea"
        RELATED = "related", "Relacionada con"
        DUPLICATES = "duplicates", "Duplica"
        REPLACES = "replaces", "Sustituye"
        DEPENDS_ON = "depends_on", "Depende de"
        REQUIREMENT = "requirement", "Es requisito de"

    source = models.ForeignKey(
        Task, on_delete=models.CASCADE, related_name="outgoing_relations"
    )
    target = models.ForeignKey(
        Task, on_delete=models.CASCADE, related_name="incoming_relations"
    )
    relation_type = models.CharField(
        max_length=20, choices=RelationType.choices
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("source", "target", "relation_type")

    def __str__(self):
        return f"{self.source_id} {self.relation_type} {self.target_id}"


class TaskActivity(models.Model):
    """Historial cronologico de cambios en una tarea."""

    class ActionType(models.TextChoices):
        CREATED = "created", "Creada"
        UPDATED = "updated", "Actualizada"
        STATE_CHANGED = "state_changed", "Cambio de estado"
        PRIORITY_CHANGED = "priority_changed", "Cambio de prioridad"
        ASSIGNED = "assigned", "Asignada"
        LABEL_ADDED = "label_added", "Etiqueta anadida"
        LABEL_REMOVED = "label_removed", "Etiqueta retirada"
        SPRINT_CHANGED = "sprint_changed", "Cambio de sprint"
        COMMENTED = "commented", "Comentada"
        CLOSED = "closed", "Cerrada"
        REOPENED = "reopened", "Reabierta"
        SUBTASK_ADDED = "subtask_added", "Subtarea anadida"
        RELATION_ADDED = "relation_added", "Relacion anadida"

    task = models.ForeignKey(
        Task, on_delete=models.CASCADE, related_name="activities"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="task_activities",
    )
    action = models.CharField(max_length=30, choices=ActionType.choices)
    field = models.CharField(max_length=50, blank=True, default="")
    old_value = models.TextField(blank=True, default="")
    new_value = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["task", "created_at"])]

    def __str__(self):
        return f"{self.task_id} {self.action} by {self.actor_id}"


class Sprint(models.Model):
    """Sprint agil con fechas y estado."""

    class SprintState(models.TextChoices):
        PLANNED = "planned", "Planificado"
        ACTIVE = "active", "Activo"
        CLOSED = "closed", "Cerrado"

    name = models.CharField(max_length=255)
    goal = models.TextField(blank=True, default="")
    description = models.TextField(blank=True, default="")
    state = models.CharField(
        max_length=10, choices=SprintState.choices, default=SprintState.PLANNED
    )
    start_date = models.DateField()
    end_date = models.DateField()
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sprints",
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="sprints",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date"]
        indexes = [models.Index(fields=["state"])]

    def __str__(self):
        return self.name


class Epic(models.Model):
    """Epica que agrupa varias tareas."""

    class EpicState(models.TextChoices):
        PLANNED = "planned", "Planificada"
        IN_PROGRESS = "in_progress", "En progreso"
        COMPLETED = "completed", "Completada"
        CANCELLED = "cancelled", "Cancelada"

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    state = models.CharField(
        max_length=15, choices=EpicState.choices, default=EpicState.PLANNED
    )
    color = models.CharField(max_length=7, default="#9c27b0")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="epics",
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="epics",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def progress(self):
        tasks = self.tasks.all()
        total = tasks.count()
        if total == 0:
            return (0, 0)
        done = tasks.filter(state=Task.State.COMPLETED).count()
        return (done, total)


class SavedSearch(models.Model):
    """Busqueda guardada con filtros para reutilizar."""

    name = models.CharField(max_length=255)
    filters = models.JSONField(default=dict)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_searches",
    )
    is_shared = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("name", "owner")

    def __str__(self):
        return self.name


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
