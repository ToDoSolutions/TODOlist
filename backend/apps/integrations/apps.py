from django.apps import AppConfig


class IntegrationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.integrations"
    verbose_name = "Integraciones"

    def ready(self):
        # Importar señales
        from . import signals  # noqa
