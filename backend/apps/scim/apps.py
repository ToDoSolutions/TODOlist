from django.apps import AppConfig


class ScimConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.scim"
    label = "scim_app"
    verbose_name = "SCIM 2.0 provisioning"
