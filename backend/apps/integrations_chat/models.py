"""Modelos para integraciones de chat (Slack, Discord)."""
from django.conf import settings
from django.db import models


class ChatIntegration(models.Model):
    """Configuración de integración con Slack o Discord."""

    class Provider(models.TextChoices):
        SLACK = "slack", "Slack"
        DISCORD = "discord", "Discord"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_integrations",
    )
    provider = models.CharField(max_length=20, choices=Provider.choices)
    webhook_url = models.URLField(help_text="Webhook URL de Slack/Discord")
    channel = models.CharField(max_length=100, blank=True, default="", help_text="Canal destino (Slack)")
    events = models.JSONField(
        default=list,
        help_text="Eventos a notificar: task_created, task_completed, sprint_started, etc.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("owner", "provider")

    def __str__(self):
        return f"{self.provider} - {self.owner.email}"


class ChatMessageLog(models.Model):
    """Log de mensajes enviados a Slack/Discord."""

    integration = models.ForeignKey(
        ChatIntegration, on_delete=models.CASCADE, related_name="message_logs"
    )
    event = models.CharField(max_length=50)
    payload = models.JSONField(default=dict)
    status_code = models.IntegerField(null=True, blank=True)
    success = models.BooleanField(default=False)
    error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.integration.provider} - {self.event} - {'OK' if self.success else 'FAIL'}"
