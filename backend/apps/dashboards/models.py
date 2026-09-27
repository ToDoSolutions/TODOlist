"""Dashboards personalizables: cada usuario configura sus widgets.

``widgets`` es un JSON array:
    [{"id": "w1", "type": "my_tasks", "title": "Mis tareas", "size": "half"},
     {"id": "w2", "type": "velocity", "title": "Velocity"}]

Los tipos disponibles se resuelven en ``resolver.py`` — cada uno produce
un dict de datos listo para renderizar en el frontend.
"""
import secrets

from django.conf import settings
from django.db import models


class Dashboard(models.Model):
    """Dashboard personalizado de un usuario."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="dashboards",
    )
    name = models.CharField(max_length=255)
    # Lista de widgets: [{id, type, title?, size?, config?}]
    widgets = models.JSONField(default=list)
    is_default = models.BooleanField(default=False)
    # Usuarios con acceso de lectura al dashboard (layout compartido;
    # los datos se resuelven siempre con el scope del que consulta).
    shared_with = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="shared_dashboards",
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.owner.email})"

    def save(self, *args, **kwargs):
        # Solo un dashboard default por usuario
        if self.is_default:
            Dashboard.objects.filter(
                owner=self.owner, is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class ShareLink(models.Model):
    """Enlace público de solo lectura a un proyecto.

    ``GET /api/public/share/{token}/`` devuelve el proyecto y sus tareas
    no archivadas sin requerir autenticación. Revocable con DELETE en
    /api/share-links/{id}/ (is_active=False).
    """

    token = models.CharField(
        max_length=64, unique=True, default=secrets.token_urlsafe,
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="share_links",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="share_links",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"share:{self.project.name} ({self.token[:8]}…)"

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)
