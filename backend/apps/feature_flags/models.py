from django.conf import settings
from django.db import models


class FeatureFlag(models.Model):
    """Feature flag para activar/desactivar funcionalidades globalmente,
    por usuario o por porcentaje de usuarios."""

    key = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_enabled = models.BooleanField(default=False)
    enabled_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="enabled_feature_flags",
    )
    enabled_percentage = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Feature flag"
        verbose_name_plural = "Feature flags"

    def __str__(self) -> str:
        return f"{self.key} ({'on' if self.is_enabled else 'off'})"
