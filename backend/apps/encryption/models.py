"""Modelos para E2E encryption: claves públicas de usuarios y tareas cifradas."""
from django.conf import settings
from django.db import models


class UserPublicKey(models.Model):
    """Clave pública de un usuario para E2E encryption (RSA/X25519)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="public_keys",
    )
    public_key = models.TextField(help_text="Clave pública en base64")
    key_id = models.CharField(max_length=100, help_text="ID único de la clave")
    algorithm = models.CharField(max_length=20, default="RSA-OA-256", help_text="Algoritmo: RSA-OA-256, X25519")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("user", "key_id")

    def __str__(self):
        return f"{self.user.email} - {self.key_id}"


class EncryptedTask(models.Model):
    """Tarea cifrada E2E: el servidor nunca ve el contenido en claro."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="encrypted_tasks",
    )
    encrypted_data = models.TextField(help_text="Datos cifrados en base64 (título, descripción, etc.)")
    encryption_key_id = models.CharField(max_length=100, help_text="ID de la clave usada para cifrar")
    iv = models.CharField(max_length=64, help_text="Vector de inicialización en base64")
    auth_tag = models.CharField(max_length=64, blank=True, default="", help_text="Tag de autenticación (GCM)")
    algorithm = models.CharField(max_length=30, default="AES-256-GCM")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"EncryptedTask {self.id} - {self.owner.email}"


class EncryptedKeyShare(models.Model):
    """Clave de cifrado de tarea cifrada con la clave pública de cada participante."""

    encrypted_task = models.ForeignKey(
        EncryptedTask, on_delete=models.CASCADE, related_name="key_shares"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="encrypted_key_shares",
    )
    encrypted_key = models.TextField(help_text="Clave AES cifrada con la clave pública del usuario")
    user_public_key = models.ForeignKey(UserPublicKey, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("encrypted_task", "user")

    def __str__(self):
        return f"KeyShare: {self.encrypted_task_id} → {self.user.email}"
