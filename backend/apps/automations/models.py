"""Modelos para automatizaciones y reglas."""
from django.conf import settings
from django.db import models


class AutomationRule(models.Model):
    """Regla de automatización: trigger → action.

    Ejemplos:
    - Cuando una tarea pasa a blocked → asignar prioridad P0
    - Cuando una tarea se completa → mover subtareas a in_progress
    - Cuando un sprint se cierra → crear el siguiente sprint
    - Cuando una tarea vence → marcar como bloqueada
    """

    class Trigger(models.TextChoices):
        TASK_CREATED = "task_created", "Tarea creada"
        TASK_STATE_CHANGED = "task_state_changed", "Estado cambiado"
        TASK_COMPLETED = "task_completed", "Tarea completada"
        TASK_BLOCKED = "task_blocked", "Tarea bloqueada"
        TASK_OVERDUE = "task_overdue", "Tarea vencida"
        COMMENT_ADDED = "comment_added", "Comentario añadido"
        SPRINT_STARTED = "sprint_started", "Sprint iniciado"
        SPRINT_CLOSED = "sprint_closed", "Sprint cerrado"
        DAILY_CHECK = "daily_check", "Chequeo diario"
        SCHEDULED = "scheduled", "Programada (cada N horas)"

    class Action(models.TextChoices):
        SET_PRIORITY = "set_priority", "Cambiar prioridad"
        SET_STATE = "set_state", "Cambiar estado"
        SET_ASSIGNEE = "set_assignee", "Asignar responsable"
        ADD_TAG = "add_tag", "Añadir etiqueta"
        SET_DUE_DATE = "set_due_date", "Establecer fecha límite"
        MOVE_TO_SPRINT = "move_to_sprint", "Mover a sprint"
        SUBTASKS_IN_PROGRESS = "subtasks_in_progress", "Subtareas a in_progress"
        CREATE_NOTIFICATION = "create_notification", "Crear notificación"
        CREATE_TASK = "create_task", "Crear tarea"
        CREATE_SUBTASK = "create_subtask", "Crear subtarea (checklist)"
        SET_DUE_OFFSET = "set_due_offset", "Fecha límite en N días"
        POST_COMMENT = "post_comment", "Publicar comentario"
        MOVE_TO_PROJECT = "move_to_project", "Mover a proyecto"
        CALL_WEBHOOK = "call_webhook", "Llamar webhook (POST)"

    class ConditionOperator(models.TextChoices):
        EQUALS = "equals", "Igual a"
        NOT_EQUALS = "not_equals", "Distinto de"
        CONTAINS = "contains", "Contiene"
        GREATER_THAN = "gt", "Mayor que"
        LESS_THAN = "lt", "Menor que"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="automation_rules",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    enabled = models.BooleanField(default=True)
    # Trigger
    trigger = models.CharField(max_length=30, choices=Trigger.choices)
    # Condiciones (JSON array of {field, operator, value})
    conditions = models.JSONField(default=list, blank=True)
    # Action
    action = models.CharField(max_length=30, choices=Action.choices)
    action_params = models.JSONField(default=dict, blank=True)
    # Para trigger SCHEDULED: intervalo en horas entre ejecuciones
    schedule_hours = models.PositiveIntegerField(
        default=24,
        help_text="Intervalo en horas para reglas SCHEDULED (p.ej. 8, 24, 168)",
    )
    # Stats
    trigger_count = models.PositiveIntegerField(default=0)
    last_triggered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.trigger} → {self.action})"


class SlaPolicy(models.Model):
    """Política SLA: tiempos objetivo por prioridad + acción de escalado.

    El daily check marca como vencidas (breach) las tareas que superan
    `resolution_hours` desde su creación y aplica la escalación:
    - bump_priority: sube la prioridad un nivel
    - notify_owner / notify_assignee: notificación de incumplimiento
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sla_policies",
    )
    name = models.CharField(max_length=255)
    priority = models.PositiveSmallIntegerField(
        help_text="Prioridad de las tareas a las que aplica (P0-P5)"
    )
    response_hours = models.PositiveIntegerField(
        default=24,
        help_text="Horas máximas hasta que la tarea se empieza (in_progress)",
    )
    resolution_hours = models.PositiveIntegerField(
        default=72,
        help_text="Horas máximas hasta que la tarea se completa",
    )
    bump_priority = models.BooleanField(
        default=True,
        help_text="Escalar prioridad un nivel al incumplir el SLA",
    )
    notify_owner = models.BooleanField(default=True)
    notify_assignee = models.BooleanField(default=True)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["priority"]
        unique_together = ("owner", "priority")

    def __str__(self):
        return f"{self.name} (P{self.priority}: {self.resolution_hours}h)"


class AutomationLog(models.Model):
    """Log de ejecución de una automatización."""

    class Status(models.TextChoices):
        SUCCESS = "success", "Éxito"
        FAILED = "failed", "Fallido"
        SKIPPED = "skipped", "Omitido"

    rule = models.ForeignKey(
        AutomationRule, on_delete=models.CASCADE, related_name="logs"
    )
    status = models.CharField(max_length=20, choices=Status.choices)
    # Contexto de la ejecución
    trigger_data = models.JSONField(default=dict, blank=True)
    action_result = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.rule.name}: {self.status}"
