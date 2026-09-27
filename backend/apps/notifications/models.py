"""Modelos para notificaciones y preferencias."""
from django.conf import settings
from django.db import models


class Notification(models.Model):
    """Notificación in-app para un usuario."""

    class Type(models.TextChoices):
        TASK_ASSIGNED = "task_assigned", "Tarea asignada"
        TASK_DUE_SOON = "task_due_soon", "Tarea por vencer"
        TASK_OVERDUE = "task_overdue", "Tarea vencida"
        TASK_COMPLETED = "task_completed", "Tarea completada"
        TASK_COMMENTED = "task_commented", "Nuevo comentario"
        TASK_BLOCKED = "task_blocked", "Tarea bloqueada"
        SPRINT_STARTED = "sprint_started", "Sprint iniciado"
        SPRINT_ENDING = "sprint_ending", "Sprint por terminar"
        SPRINT_CLOSED = "sprint_closed", "Sprint cerrado"
        MENTION = "mention", "Mención en comentario"
        PR_OPENED = "pr_opened", "PR abierto"
        PR_MERGED = "pr_merged", "PR fusionado"
        PR_REVIEW_REQUESTED = "pr_review_requested", "Review solicitada"
        CI_FAILED = "ci_failed", "CI fallida"
        RELEASE_PUBLISHED = "release_published", "Release publicada"
        AUTOMATION_TRIGGERED = "automation_triggered", "Automatización ejecutada"
        CUSTOM = "custom", "Personalizada"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    type = models.CharField(max_length=30, choices=Type.choices, default=Type.CUSTOM)
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True, default="")
    # Enlace opcional a una tarea o sprint
    task = models.ForeignKey(
        "tasks.Task", on_delete=models.CASCADE, null=True, blank=True,
        related_name="notifications",
    )
    sprint = models.ForeignKey(
        "tasks.Sprint", on_delete=models.CASCADE, null=True, blank=True,
        related_name="notifications",
    )
    # URL para navegación (ej: /app/tasks/123)
    action_url = models.CharField(max_length=500, blank=True, default="")
    # Metadata adicional
    metadata = models.JSONField(default=dict, blank=True)
    read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    # Canal por el que se envió
    sent_in_app = models.BooleanField(default=True)
    sent_email = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "read"]),
            models.Index(fields=["recipient", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.recipient.username}: {self.title}"


class NotificationPreference(models.Model):
    """Preferencias de notificación por usuario y tipo."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_preferences",
    )
    notification_type = models.CharField(max_length=30)
    # Canales
    in_app_enabled = models.BooleanField(default=True)
    email_enabled = models.BooleanField(default=False)
    # Digest: agrupar notificaciones
    digest_enabled = models.BooleanField(default=False)
    # Frecuencia del digest (ClickUp permite diario/semanal)
    digest_frequency = models.CharField(
        max_length=10,
        choices=[("daily", "Diario"), ("weekly", "Semanal")],
        default="daily",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "notification_type")

    def __str__(self):
        return f"{self.user.username}: {self.notification_type}"


class PushSubscription(models.Model):
    """Suscripción Web Push (navegador) de un usuario.

    Una fila por endpoint de navegador: el endpoint es único globalmente
    y se reasigna si otro usuario lo registra (mismo dispositivo, otra
    sesión de usuario).
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="push_subscriptions",
    )
    endpoint = models.TextField(unique=True)
    p256dh = models.CharField(max_length=200)
    auth = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username}: {self.endpoint[:60]}"
