"""Formularios de intake: creación de tareas para usuarios no técnicos.

Un IntakeForm define un esquema JSON de campos; cada submission valida el
schema y crea una Task en el proyecto destino. Los campos no mapeados a
atributos de la tarea se formatean en la descripción.

Schema ejemplo::

    [
      {"name": "titulo", "label": "Título", "type": "text", "required": true},
      {"name": "urgencia", "label": "Urgencia", "type": "select",
       "options": ["baja", "media", "alta"], "required": true}
    ]

Campos especiales mapeados a Task: ``title``, ``description``,
``priority``, ``due_date``, ``assignee``. El resto va al cuerpo
de la descripción como "Label: valor".
"""
import secrets

from django.conf import settings
from django.db import models


class IntakeForm(models.Model):
    """Definición de un formulario de intake."""

    FIELD_TYPES = ["text", "textarea", "number", "date", "select", "checkbox"]
    RESERVED = {"title", "description", "priority", "due_date", "assignee"}

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="intake_forms",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="intake_forms",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    # Esquema de campos: [{name, label, type, required, options?, default?}]
    schema = models.JSONField(default=list)
    # Defaults aplicados a la tarea creada (state, priority, task_type, tags)
    task_defaults = models.JSONField(default=dict, blank=True)
    enabled = models.BooleanField(default=True)
    # Token opaco para el endpoint público de submissions
    # (POST /api/intake-forms/public/{token}/submit/). Rotable por el owner
    # vía POST /api/intake-forms/{id}/rotate_public_token/.
    public_token = models.CharField(
        max_length=64, unique=True, null=True, blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} → {self.project.name}"

    def save(self, *args, **kwargs):
        if not self.public_token:
            self.public_token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    def validate_schema(self):
        """Valida el esquema del formulario. Devuelve lista de errores."""
        errors = []
        if not isinstance(self.schema, list) or not self.schema:
            return ["schema debe ser una lista no vacía de campos"]
        seen = set()
        for i, field in enumerate(self.schema):
            name = field.get("name", "")
            if not name:
                errors.append(f"campo {i}: name requerido")
            elif name in seen:
                errors.append(f"campo '{name}' duplicado")
            seen.add(name)
            if field.get("type", "text") not in self.FIELD_TYPES:
                errors.append(
                    f"campo '{name}': type inválido '{field.get('type')}'"
                )
            if field.get("type") == "select" and not field.get("options"):
                errors.append(f"campo '{name}': select requiere options")
        return errors


class IntakeSubmission(models.Model):
    """Registro de una submission de formulario (auditoría + trazabilidad)."""

    form = models.ForeignKey(
        IntakeForm, on_delete=models.CASCADE, related_name="submissions"
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="intake_submissions",
    )
    data = models.JSONField(default=dict)
    task = models.ForeignKey(
        "tasks.Task",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="intake_submissions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.form.name} #{self.id}"
