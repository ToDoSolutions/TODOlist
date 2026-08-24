"""Modelos para sync offline con conflict resolution."""
from django.conf import settings
from django.db import models


class SyncDevice(models.Model):
    """Dispositivo registrado para sync offline."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sync_devices",
    )
    device_id = models.CharField(max_length=100, unique=True)
    device_name = models.CharField(max_length=200, blank=True, default="")
    last_sync_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - {self.device_id}"


class SyncOperation(models.Model):
    """Operación de sync: create/update/delete realizada offline."""

    class OpType(models.TextChoices):
        CREATE = "create", "Crear"
        UPDATE = "update", "Actualizar"
        DELETE = "delete", "Eliminar"

    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        APPLIED = "applied", "Aplicada"
        CONFLICT = "conflict", "Conflicto"
        REJECTED = "rejected", "Rechazada"

    device = models.ForeignKey(SyncDevice, on_delete=models.CASCADE, related_name="operations")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sync_operations",
    )
    op_type = models.CharField(max_length=10, choices=OpType.choices)
    entity_type = models.CharField(max_length=50, help_text="task, project, comment, etc.")
    entity_id = models.CharField(max_length=100, help_text="Client-side UUID")
    server_entity_id = models.BigIntegerField(null=True, blank=True)
    payload = models.JSONField(default=dict, help_text="Datos de la entidad")
    client_timestamp = models.DateTimeField()
    server_timestamp = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    conflict_data = models.JSONField(null=True, blank=True, help_text="Datos del servidor en conflicto")
    created_at = models.DateTimeField(auto_now_add=True)
    applied_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"], name="sync_op_user_status_idx"),
            models.Index(fields=["device", "status"], name="sync_op_dev_status_idx"),
        ]

    def __str__(self):
        return f"{self.op_type} {self.entity_type} - {self.status}"
