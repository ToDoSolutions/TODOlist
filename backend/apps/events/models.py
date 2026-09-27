"""Outbox transaccional: eventos de dominio durables para efectos externos.

Los efectos internos de negocio (TaskActivity, AuditLog, Notification,
AutomationLog) se escriben en la MISMA transacción que el cambio y deben
seguir síncronos. El outbox cubre los efectos EXTERNOS fallibles (push
WebSocket, webhooks salientes): el evento se persiste atómicamente con el
cambio y el dispatcher lo entrega a los handlers con reintentos.
"""
import uuid

from django.db import models


class OutboxEvent(models.Model):
    """Evento de dominio pendiente de entregar a handlers externos."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        PROCESSED = "processed", "Procesado"
        FAILED = "failed", "Fallido"  # reintentable por el beat

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_type = models.CharField(max_length=60, db_index=True)
    # Correlation id end-to-end: propaga request → outbox → handler → log
    correlation_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    # Idempotencia: dos saves no deben producir dos entregas si se deduplica
    idempotency_key = models.CharField(max_length=120, unique=True, null=True, blank=True)
    payload = models.JSONField(default=dict)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self):
        return f"{self.event_type} ({self.status})"
