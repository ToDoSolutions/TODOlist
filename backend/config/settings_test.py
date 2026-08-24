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
