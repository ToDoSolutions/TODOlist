"""Settings para tests: SQLite en memoria, sin Redis ni PG."""
from config.settings import *
from config.settings import BASE_DIR, REST_FRAMEWORK

DEBUG = True
SECRET_KEY = "test-secret-key-for-pytest-only-64bytes-aaaaaaaaaaaaaaaaaaaaaaaa"

# Los tests no sirven HTTPS: sin esto SecurityMiddleware redirige 301→https
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "test.sqlite3",
    }
}

# Desactivar migraciones lentas en tests
class DisableMigrations:
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


MIGRATION_MODULES = DisableMigrations()

# SERVE_PERMISSIONS se evaluó en settings.py con DEBUG=False (IsAdminUser);
# en tests DEBUG=True → cualquier autenticado puede ver schema/docs.
SPECTACULAR_SETTINGS["SERVE_PERMISSIONS"] = ["rest_framework.permissions.IsAuthenticated"]

# Sin throttling ni paginación para tests más simples
REST_FRAMEWORK["DEFAULT_PAGINATION_CLASS"] = None
REST_FRAMEWORK["PAGE_SIZE"] = None
REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = ()

# Cache en memoria para tests (sin Redis)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "test",
    }
}

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

# SCIM 2.0 habilitado en tests (equivale a SCIM_ENABLED=1 + tokens en
# config.settings, aplicado aquí porque la condición de settings.py ya
# se evaluó en el import).
SCIM_ENABLED = True
SCIM_TOKENS = ["test-scim-token-0123456789abcdef"]
INSTALLED_APPS += ["apps.scim", "django_scim"]
MIDDLEWARE += ["apps.scim.middleware.SCIMBearerAuthMiddleware"]
SCIM_SERVICE_PROVIDER = {
    "NETLOC": "testserver",
    "SCHEME": "http",
    "USER_ADAPTER": "apps.scim.adapters.SCIMUserAdapter",
    "GROUP_MODEL": "apps.collaboration.models.Organization",
    "GROUP_ADAPTER": "apps.scim.adapters.SCIMOrganizationAdapter",
    "WWW_AUTHENTICATE_HEADER": 'Bearer realm="scim"',
    "AUTHENTICATION_SCHEMES": [
        {
            "type": "oauthbearertoken",
            "name": "OAuth Bearer Token",
            "description": "Token estático SCIM",
            "specUri": "https://www.rfc-editor.org/rfc/rfc6750",
        }
    ],
}

