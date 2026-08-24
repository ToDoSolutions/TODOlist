from django.conf import settings
from django.db import models

from apps.tasks.models import Task


class AiSuggestion(models.Model):
    """Sugerencia generada por el asistente de IA para una tarea o usuario."""

    class SuggestionType(models.TextChoices):
        PRIORITY_ESTIMATE = "priority_estimate", "Estimacion de prioridad"
        STORY_POINT_ESTIMATE = "story_point_estimate", "Estimacion de story points"
        BLOCKER_DETECTION = "blocker_detection", "Deteccion de bloqueos"
        DESCRIPTION_IMPROVEMENT = "description_improvement", "Mejora de descripcion"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_suggestions",
    )
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="ai_suggestions",
    )
    suggestion_type = models.CharField(
        max_length=30, choices=SuggestionType.choices
    )
    input_data = models.JSONField(default=dict, blank=True)
    output_data = models.JSONField(default=dict, blank=True)
    confidence = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "suggestion_type"], name="ai_sugg_user_type_idx"),
            models.Index(fields=["task"], name="ai_sugg_task_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.suggestion_type} for {self.user_id} on {self.task_id}"
