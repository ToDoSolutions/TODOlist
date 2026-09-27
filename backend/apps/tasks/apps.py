from django.apps import AppConfig


class TasksConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tasks"
    verbose_name = "Tareas"

    def ready(self):
        # Registrar signals de eventos WebSocket
        # Registrar signals de watchers / multi-assignee
        from . import (
            signals,  # noqa: F401
            ws_signals,  # noqa: F401
        )
