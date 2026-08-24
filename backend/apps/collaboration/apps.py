from django.apps import AppConfig


class CollaborationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.collaboration"
    verbose_name = "Colaboración"

    def ready(self):
        from . import signals  # noqa: F401
