from django.conf import settings
from django.db import models


class Tag(models.Model):
    """Etiqueta personalizada, coloreada y propiedad del usuario."""

    name = models.CharField(max_length=64)
    color = models.CharField(max_length=7, default="#1976d2")  # hex
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tags",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("name", "owner")
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name
