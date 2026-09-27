from django.apps import AppConfig


class AutomationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.automations"
    verbose_name = "Automatizaciones"

    def ready(self):
        from . import signals  # noqa: F401
