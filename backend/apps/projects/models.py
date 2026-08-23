from django.conf import settings
from django.db import models


class Project(models.Model):
    """Proyecto que agrupa tareas. Puede archivarse."""

    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, default="")
    color = models.CharField(max_length=7, default="#1976d2")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="projects",
    )
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name
