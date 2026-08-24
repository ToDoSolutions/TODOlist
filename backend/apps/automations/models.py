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
    # Stats
    trigger_count = models.PositiveIntegerField(default=0)
    last_triggered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.trigger} → {self.action})"


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
