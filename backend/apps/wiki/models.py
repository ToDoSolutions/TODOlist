"""Wiki integrada: páginas de documentación por proyecto o personales.

Jerarquía mediante ``parent`` (página padre) — permite estructuras tipo
Confluence: Arquitectura → API → Guías. El contenido es markdown; el
render lo hace el frontend.
"""
from django.conf import settings
from django.db import models


class WikiPage(models.Model):
    """Página de wiki vinculada a un proyecto (o personal si project=None)."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wiki_pages",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="wiki_pages",
        null=True,
        blank=True,
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
    )
    title = models.CharField(max_length=255)
    content = models.TextField(blank=True, default="")
    is_published = models.BooleanField(default=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="wiki_edits",
    )
    version = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["project_id", "parent_id", "title"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.pk:
            self.version = (self.version or 1) + 1
        super().save(*args, **kwargs)
