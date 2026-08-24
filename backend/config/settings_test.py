"""Settings para tests: SQLite en memoria, sin Redis ni PG."""
from config.settings import *  # noqa
import os

DEBUG = True
SECRET_KEY = "test-secret-key"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Desactivar migraciones lentas en tests
class DisableMigrations:
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


MIGRATION_MODULES = DisableMigrations()

# Sin throttling ni paginación para tests más simples
REST_FRAMEWORK["DEFAULT_PAGINATION_CLASS"] = None
REST_FRAMEWORK["PAGE_SIZE"] = None

# Email backend en memoria
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Sin password validation para tests rápidos
AUTH_PASSWORD_VALIDATORS = []

# Celery: ejecutar tareas síncronamente en tests
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_URL = "memory://"

# GitHub: sin credenciales reales en tests
GITHUB_APP_ID = "test-app-id"
GITHUB_APP_PRIVATE_KEY = ""
GITHUB_APP_CLIENT_ID = "test-client-id"
GITHUB_APP_CLIENT_SECRET = "test-client-secret"
GITHUB_APP_WEBHOOK_SECRET = "test-webhook-secret"

