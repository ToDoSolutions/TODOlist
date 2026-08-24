"""Modelo para idempotencia y tracking de webhooks de GitHub."""
from django.db import models


class WebhookDelivery(models.Model):
    """Registra cada entrega de webhook para idempotencia y reintentos.

    GitHub envía un ID de entrega (X-GitHub-Delivery) que es único
    por evento. Lo usamos para evitar procesar el mismo evento dos veces.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        PROCESSED = "processed", "Procesado"
        FAILED = "failed", "Fallido"
        RETRYING = "retrying", "Reintentando"
        DEAD_LETTER = "dead_letter", "Cola de mensajes fallidos"

    delivery_id = models.CharField(max_length=100, unique=True, db_index=True)
    event_type = models.CharField(max_length=50)
    action = models.CharField(max_length=50, blank=True, default="")
    payload = models.JSONField(default=dict)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    error_message = models.TextField(blank=True, default="")
    retry_count = models.PositiveIntegerField(default=0)
    max_retries = models.PositiveIntegerField(default=5)

    # Repositorio afectado (para auditoría)
    repo_full_name = models.CharField(max_length=255, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    next_retry_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["next_retry_at"]),
        ]

    def __str__(self):
        return f"{self.delivery_id} ({self.event_type}/{self.action}) = {self.status}"

    @property
    def is_dead(self):
        return self.status == self.Status.DEAD_LETTER

    @property
    def can_retry(self):
        return self.retry_count < self.max_retries and not self.is_dead
