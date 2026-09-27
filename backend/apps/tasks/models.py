from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.projects.models import Project, ProjectSection
from apps.tags.models import Tag


class TaskQuerySet(models.QuerySet):
    def for_user(self, user, write=False):
        """Tareas accesibles por el usuario.

        Incluye las propias y las de proyectos donde es miembro.
        Con ``write=True`` solo proyectos donde tiene rol editor/owner
        (los viewers solo pueden leer).
        """
        from django.db.models import Q

        qs = Q(owner=user)
        if write:
            qs |= Q(
                project__members__user=user,
                project__members__role__in=["owner", "editor"],
            )
            # Org owner/admin → escritura en proyectos de la organización
            qs |= Q(
                project__organization__memberships__user=user,
                project__organization__memberships__role__in=["owner", "admin"],
            )
            # Multi-assignee: los asignados pueden editar la tarea
            qs |= Q(assignees=user)
        else:
            qs |= Q(project__members__user=user)
            # Org member → lectura en proyectos de la organización
            qs |= Q(
                project__organization__memberships__user=user,
                project__organization__memberships__role__in=["owner", "admin", "member"],
            )
            # Asignados y watchers pueden leer la tarea
            qs |= Q(assignees=user) | Q(watchers=user)
        return self.filter(qs).distinct()


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
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recurrence_rules",
        null=True,
        blank=True,
    )

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
            # Meses calendario reales (timedelta(days=30) derivaba: feb=28d)
            from dateutil.relativedelta import relativedelta
            return base + relativedelta(months=self.interval)
        elif self.frequency == self.Frequency.YEARLY:
            # Años calendario reales (timedelta(days=365) falla en bisiestos)
            from dateutil.relativedelta import relativedelta
            return base + relativedelta(years=self.interval)
        return None

    def should_continue(self):
        """Determina si la regla debe seguir generando ocurrencias.
        Se llama DESPUÉS de incrementar occurrences_generated.
        """
        if self.until and timezone.now() > self.until:
            return False
        return not (self.count and self.occurrences_generated >= self.count)


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

    # Orden manual en la vista de lista (drag & drop, ordering=position)
    position = models.PositiveIntegerField(default=0)

    # Fijar arriba de la lista (Linear/Todoist "pin"): ordena antes que el
    # resto cuando el ordering por defecto incluye -is_pinned.
    is_pinned = models.BooleanField(default=False)

    # Hito (Asana/Jira): la tarea marca un punto de control en el roadmap.
    is_milestone = models.BooleanField(default=False)

    # Favoritos por usuario (estrella Jira/Asana): M2M porque en proyectos
    # compartidos cada miembro tiene sus propios favoritos.
    favorited_by = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="favorite_tasks",
        help_text="Usuarios que marcaron la tarea como favorita",
    )

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
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tasks",
        help_text="Usuario asignado a la tarea",
    )
    # Multi-asignación: responsables adicionales (el FK assignee sigue
    # siendo el responsable principal)
    assignees = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="assigned_tasks_multi",
        help_text="Usuarios asignados adicionales a la tarea",
    )
    # Watchers: usuarios que siguen la tarea (lectura + notificaciones)
    watchers = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="watched_tasks",
        help_text="Usuarios que observan la tarea",
    )
    # Recordatorio puntual (lo envía el beat send-due-reminders)
    reminder_at = models.DateTimeField(null=True, blank=True)
    reminder_sent = models.BooleanField(default=False)
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
    # Sección dentro del proyecto (columnas tipo Todoist/Asana).
    # Debe pertenecer al mismo proyecto que la tarea (validado en el
    # serializer); al borrar la sección la tarea queda sin sección.
    section = models.ForeignKey(
        ProjectSection,
        on_delete=models.SET_NULL,
        related_name="tasks",
        null=True,
        blank=True,
    )
    # Secuencia por proyecto para refs legibles (estilo Linear/Jira:
    # "MP-12"). Se asigna en TaskViewSet.perform_create como
    # max(seq del proyecto)+1; 0 = sin asignar (tareas antiguas o
    # creadas fuera del API) y el ref cae al id.
    # NO hay unique_together (project, seq): updates masivos/reorders
    # podrían colisionar transitoriamente.
    seq = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    version = models.IntegerField(default=1, help_text="Versión del recurso, se incrementa en cada save")

    objects = TaskQuerySet.as_manager()

    class Meta:
        # Las fijadas van primero en el orden por defecto (pin al top).
        ordering = ["-is_pinned", "-created_at"]
        indexes = [
            models.Index(fields=["state"]),
            models.Index(fields=["priority"]),
            models.Index(fields=["due_date"]),
            models.Index(fields=["task_type"]),
            models.Index(fields=["sprint"]),
            models.Index(fields=["epic"]),
            models.Index(fields=["parent"]),
            # Compuestos para las vistas calientes (kanban, métricas,
            # calendario): el filtro dominante es siempre owner/project+state
            models.Index(fields=["owner", "state"], name="task_owner_state_idx"),
            models.Index(fields=["project", "state"], name="task_proj_state_idx"),
            models.Index(fields=["owner", "due_date"], name="task_owner_due_idx"),
            models.Index(fields=["sprint", "state"], name="task_sprint_state_idx"),
            models.Index(fields=["owner", "completed_at"], name="task_owner_done_idx"),
        ]

    def __str__(self) -> str:
        return self.title

    def save(self, *args, **kwargs):
        """Incrementa la versión en cada save (excepto si se indica lo contrario)."""
        increment = kwargs.pop("increment_version", True)
        if increment and self.pk:
            # Solo incrementar si ya existe (update), no en create
            self.version = (self.version or 1) + 1
        super().save(*args, **kwargs)

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
        """Progreso de subtareas: (completadas, total).

        Itera en memoria para aprovechar prefetch_related: filter().count()
        lanzaría una query por tarea aunque la relación esté precargada.
        """
        children = list(self.subtasks_children.all())
        if not children:
            return (0, 0)
        done = sum(
            1 for c in children
            if c.state in (Task.State.COMPLETED, Task.State.CANCELLED)
        )
        return (done, len(children))


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
    # Respuestas anidadas (un nivel de threading como en Linear/Slack)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="replies",
    )
    # Reacciones emoji: {"👍": [user_id, ...], "🎉": [...]}
    reactions = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Comentario en {self.task_id} por {self.author_id}"


class TimeEntry(models.Model):
    """Registro de tiempo trabajado en una tarea."""

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="time_entries")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="time_entries",
    )
    duration_seconds = models.PositiveIntegerField(default=0)
    description = models.TextField(blank=True, default="")
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    # Cronómetro en vivo: solo una entrada running por usuario (se fuerza
    # en el endpoint timer_start, no hace falta constraint)
    is_running = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} - {self.duration_seconds}s on {self.task_id}"


class Attachment(models.Model):
    """Adjunto en una tarea o comentario."""

    task = models.ForeignKey(
        Task, on_delete=models.CASCADE, null=True, blank=True, related_name="attachments"
    )
    comment = models.ForeignKey(
        Comment, on_delete=models.CASCADE, null=True, blank=True, related_name="attachments"
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    file = models.FileField(upload_to="attachments/", blank=True)
    external_url = models.URLField(blank=True, default="")
    filename = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(default=0)
    content_type = models.CharField(max_length=100, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.filename


class TaskTemplate(models.Model):
    """Plantilla reutilizable para crear tareas con campos predefinidos."""

    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, default="")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="task_templates",
    )
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, null=True, blank=True, related_name="templates"
    )
    template_data = models.JSONField(
        default=dict,
        help_text="Campos predefinidos: title, description, priority, state, etc.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def create_task(self, user, overrides=None):
        """Crea una tarea a partir de la plantilla."""
        data = dict(self.template_data)
        if overrides:
            data.update(overrides)
        project = self.project or Project.objects.filter(owner=user).first()
        return Task.objects.create(
            owner=user,
            project=project,
            title=data.get("title", self.name),
            description=data.get("description", ""),
            priority=data.get("priority", 3),
            state=data.get("state", "pending"),
        )


class CustomField(models.Model):
    """Campo personalizado por proyecto."""

    class FieldType(models.TextChoices):
        TEXT = "text", "Texto"
        NUMBER = "number", "Número"
        DATE = "date", "Fecha"
        SELECT = "select", "Selección"
        MULTISELECT = "multiselect", "Multi-selección"
        URL = "url", "URL"
        CHECKBOX = "checkbox", "Checkbox"

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="custom_fields"
    )
    name = models.CharField(max_length=120)
    field_type = models.CharField(max_length=20, choices=FieldType.choices)
    options = models.JSONField(default=list, blank=True, help_text="Opciones para select/multiselect")
    is_required = models.BooleanField(default=False)
    default_value = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("project", "name")

    def __str__(self):
        return f"{self.project.name} - {self.name}"


class CustomFieldValue(models.Model):
    """Valor de un campo personalizado en una tarea."""

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="custom_field_values")
    field = models.ForeignKey(CustomField, on_delete=models.CASCADE)
    value = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("task", "field")

    def __str__(self):
        return f"{self.task_id}: {self.field.name} = {self.value}"


class OutgoingWebhook(models.Model):
    """Webhook saliente: notifica a servicios externos de eventos."""

    class Event(models.TextChoices):
        TASK_CREATED = "task_created", "Tarea creada"
        TASK_UPDATED = "task_updated", "Tarea actualizada"
        TASK_COMPLETED = "task_completed", "Tarea completada"
        TASK_DELETED = "task_deleted", "Tarea eliminada"
        COMMENT_ADDED = "comment_added", "Comentario añadido"
        SPRINT_STARTED = "sprint_started", "Sprint iniciado"
        SPRINT_CLOSED = "sprint_closed", "Sprint cerrado"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="outgoing_webhooks",
    )
    url = models.URLField()
    events = models.JSONField(default=list, help_text="Lista de eventos a notificar")
    secret = models.CharField(max_length=100, blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.url} ({', '.join(self.events)})"


class TaskApproval(models.Model):
    """Solicitud de aprobación sobre una tarea (paridad Asana/Monday).

    El requester pide a un ``approver`` que decida; solo el approver del
    ÚLTIMO approval pendiente puede aprobar/rechazar (enforcement en el
    ViewSet: approve/reject).
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        APPROVED = "approved", "Aprobada"
        REJECTED = "rejected", "Rechazada"

    task = models.ForeignKey(
        Task, on_delete=models.CASCADE, related_name="approvals"
    )
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="approvals_requested",
    )
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="approvals_to_decide",
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING
    )
    note = models.TextField(blank=True, default="")
    decision_note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        # -id como desempate: created_at puede repetirse en el mismo tick
        # del reloj (mismo criterio que ProjectStatusUpdate) y el "último
        # pendiente" que decide approve/reject debe ser determinista.
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return (
            f"Aprobación {self.status} de tarea {self.task_id} "
            f"(approver {self.approver_id})"
        )
