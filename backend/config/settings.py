"""Django settings for TODOlist backend."""
from pathlib import Path
import os
import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1", "backend"]),
    DJANGO_CORS_ALLOW_ALL=(bool, True),
    DJANGO_FRONTEND_URL=(str, "http://localhost:5173"),
    GITHUB_APP_ID=(str, ""),
    GITHUB_APP_PRIVATE_KEY=(str, ""),
    GITHUB_APP_CLIENT_ID=(str, ""),
    GITHUB_APP_CLIENT_SECRET=(str, ""),
    GITHUB_APP_WEBHOOK_SECRET=(str, ""),
    GITHUB_APP_NAME=(str, "todolist-app"),
)
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-insecure-change-me")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")

# Validación: en producción la SECRET_KEY no puede ser el valor por defecto
if not DEBUG and SECRET_KEY == "dev-insecure-change-me":
    raise RuntimeError("DJANGO_SECRET_KEY debe configurarse en producción")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",

    # Local
    "apps.users",
    "apps.projects",
    "apps.tasks",
    "apps.tags",
    "apps.integrations",
    "apps.notifications",
    "apps.automations",
    "apps.collaboration",
    "apps.graphql_app",
    "drf_spectacular",
    "graphene_django",
    "channels",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Database
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", default="todolist"),
        "USER": env("POSTGRES_USER", default="todolist"),
        "PASSWORD": env("POSTGRES_PASSWORD", default="todolist"),
        "HOST": env("POSTGRES_HOST", default="db"),
        "PORT": env("POSTGRES_PORT", default="5432"),
    }
}

# Custom user model
AUTH_USER_MODEL = "users.User"

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es-es"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# DRF
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "apps.users.api_auth.APIKeyAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "MAX_PAGE_SIZE": 100,
    "DEFAULT_THROTTLE_CLASSES": (
        "apps.users.api_auth.BurstRateThrottle",
        "apps.users.api_auth.AuthenticatedRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "burst": "60/min",
        "authenticated": "300/hour",
        "api_key": "1000/hour",
    },
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "TODOlist API",
    "DESCRIPTION": "API REST para gestión de tareas, proyectos, sprints y integración con GitHub.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "TAGS": [
        {"name": "tasks", "description": "Tareas"},
        {"name": "projects", "description": "Proyectos"},
        {"name": "sprints", "description": "Sprints"},
        {"name": "epics", "description": "Épicas"},
        {"name": "tags", "description": "Etiquetas"},
        {"name": "integrations", "description": "Integraciones"},
        {"name": "notifications", "description": "Notificaciones"},
        {"name": "automations", "description": "Automatizaciones"},
        {"name": "collaboration", "description": "Colaboración"},
        {"name": "metrics", "description": "Métricas"},
        {"name": "auth", "description": "Autenticación"},
    ],
}

from datetime import timedelta
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}

# CORS
CORS_ALLOW_ALL_ORIGINS = env("DJANGO_CORS_ALLOW_ALL")
CORS_ALLOWED_ORIGINS = [env("DJANGO_FRONTEND_URL")]
DJANGO_FRONTEND_URL = env("DJANGO_FRONTEND_URL")

# Celery
CELERY_BROKER_URL = f"redis://{env('REDIS_HOST', default='redis')}:6379/0"
CELERY_RESULT_BACKEND = f"redis://{env('REDIS_HOST', default='redis')}:6379/0"

# Caching con Redis
REDIS_HOST = env("REDIS_HOST", default="redis")
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"redis://{REDIS_HOST}:6379/1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
        "KEY_PREFIX": "todolist",
        "TIMEOUT": 300,  # 5 minutos por defecto
    }
}

# Channels (WebSocket)
ASGI_APPLICATION = "config.asgi.application"
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [(REDIS_HOST, 6379)],
        },
    },
}

# GraphQL
GRAPHENE = {
    "SCHEMA": "apps.graphql_app.schema.schema",
    "MIDDLEWARE": [],
}
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

# Celery Beat: tareas periódicas
CELERY_BEAT_SCHEDULE = {
    "sync-github-issues": {
        "task": "apps.integrations.tasks.sync_all_github_issues",
        "schedule": 300.0,  # cada 5 minutos
    },
    "retry-pending-webhooks": {
        "task": "apps.integrations.tasks.process_pending_webhook_retries",
        "schedule": 60.0,  # cada minuto
    },
    "daily-automation-check": {
        "task": "apps.automations.tasks.run_daily_checks_task",
        "schedule": 3600.0,  # cada hora
    },
}

# GitHub App
GITHUB_APP_ID = env("GITHUB_APP_ID")
GITHUB_APP_PRIVATE_KEY = env("GITHUB_APP_PRIVATE_KEY")
GITHUB_APP_CLIENT_ID = env("GITHUB_APP_CLIENT_ID")
GITHUB_APP_CLIENT_SECRET = env("GITHUB_APP_CLIENT_SECRET")
GITHUB_APP_WEBHOOK_SECRET = env("GITHUB_APP_WEBHOOK_SECRET")
GITHUB_APP_NAME = env("GITHUB_APP_NAME")
