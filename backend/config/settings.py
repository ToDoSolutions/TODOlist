"""Django settings for TODOlist backend."""
import os
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1", "backend"]),
    DJANGO_CORS_ALLOW_ALL=(bool, False),
    DJANGO_FRONTEND_URL=(str, "http://localhost:5173"),
    GITHUB_APP_ID=(str, ""),
    GITHUB_APP_PRIVATE_KEY=(str, ""),
    GITHUB_APP_CLIENT_ID=(str, ""),
    GITHUB_APP_CLIENT_SECRET=(str, ""),
    GITHUB_APP_WEBHOOK_SECRET=(str, ""),
    GITHUB_APP_NAME=(str, "todolist-app"),
    VAPID_PUBLIC_KEY=(str, ""),
    VAPID_PRIVATE_KEY=(str, ""),
    VAPID_CLAIMS_SUBJECT=(str, "mailto:admin@todolist.local"),
)
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-insecure-change-me")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")

# Validación: en producción la SECRET_KEY no puede ser el valor por defecto
if not DEBUG and SECRET_KEY == "dev-insecure-change-me":
    raise RuntimeError("DJANGO_SECRET_KEY debe configurarse en producción")

# Claves de cifrado de datos (AES-256-GCM) desacopladas de SECRET_KEY.
# Lista ordenada: la ÚLTIMA es la activa para escritura; todas las anteriores
# siguen siendo válidas para lectura (rotación progresiva).
# Si está vacío, se deriva una clave de SECRET_KEY (fallback de desarrollo).
DATA_ENCRYPTION_KEYS = env.list("DATA_ENCRYPTION_KEYS", default=[])
if not DEBUG and not DATA_ENCRYPTION_KEYS:
    raise RuntimeError(
        "DATA_ENCRYPTION_KEYS debe configurarse en producción "
        "(lista separada por comas; la última es la clave activa)"
    )

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",  # full-text search (SearchVector)

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
    "apps.social_auth",
    "apps.feature_flags",
    "apps.ai_assistant",
    "apps.okrs",
    "apps.integrations_chat",
    "apps.monitoring",
    "apps.offline_sync",
    "apps.encryption",
    "apps.wiki",
    "apps.intake",
    "apps.dashboards",
    "apps.events",
    "apps.mcp",
    "apps.caldav",
    "drf_spectacular",
    "graphene_django",
    "channels",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "allauth.socialaccount.providers.github",
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
    "allauth.account.middleware.AccountMiddleware",
    "apps.monitoring.middleware.MetricsMiddleware",
    "apps.monitoring.security_headers.SecurityHeadersMiddleware",
    "apps.feature_flags.middleware.FeatureFlagMiddleware",
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
if env.bool("USE_SQLITE", default=False):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
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
        "apps.users.cookie_auth.CookieJWTAuthentication",
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "apps.users.api_auth.APIKeyAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
        "apps.users.api_auth.APIKeyScopePermission",
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
        "apps.users.api_auth.APIKeyRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "burst": env("DJANGO_THROTTLE_BURST", default="60/min"),
        "authenticated": env("DJANGO_THROTTLE_AUTHENTICATED", default="300/hour"),
        "api_key": env("DJANGO_THROTTLE_API_KEY", default="1000/hour"),
        "login": env("DJANGO_THROTTLE_LOGIN", default="10/min"),
        "anon": env("DJANGO_THROTTLE_ANON", default="30/min"),
        "register": env("DJANGO_THROTTLE_REGISTER", default="5/hour"),
        "password_reset": env("DJANGO_THROTTLE_PASSWORD_RESET", default="5/hour"),
        # Canales públicos de entrada (sin auth): límites por IP
        "intake_public": env("DJANGO_THROTTLE_INTAKE_PUBLIC", default="20/hour"),
        "public_share": env("DJANGO_THROTTLE_PUBLIC_SHARE", default="60/hour"),
        # Acciones sensibles autenticadas (confirmación por contraseña):
        # desactivar/eliminar cuenta — frena fuerza bruta sobre sesiones
        "sensitive_action": env("DJANGO_THROTTLE_SENSITIVE", default="5/hour"),
        "inbound": env("DJANGO_THROTTLE_INBOUND", default="60/hour"),
    },
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "TODOlist API",
    "DESCRIPTION": "API REST para gestión de tareas, proyectos, sprints y integración con GitHub.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    # Schema/docs solo para autenticados (o solo staff en producción)
    "SERVE_PERMISSIONS": (
        ["rest_framework.permissions.IsAuthenticated"]
        if DEBUG
        else ["rest_framework.permissions.IsAdminUser"]
    ),
    "POSTPROCESSING_HOOKS": [
        "config.schema_hooks.add_auth_responses",
    ],
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
# Necesario para enviar cookies httpOnly cross-origin (SPA en otro puerto)
CORS_ALLOW_CREDENTIALS = True

# Cookies de autenticación JWT (httpOnly)
AUTH_COOKIE_SECURE = not DEBUG

# --- Quotas de uso ---
ATTACHMENT_MAX_SIZE = env.int("ATTACHMENT_MAX_SIZE", default=10 * 1024 * 1024)  # 10MB
MAX_AUTOMATION_RULES_PER_USER = env.int("MAX_AUTOMATION_RULES_PER_USER", default=100)
# Frecuencia mínima entre escrituras de APIKey.last_used_at (evita hot writes)
APIKEY_LAST_USED_THROTTLE_SECONDS = env.int("APIKEY_LAST_USED_THROTTLE_SECONDS", default=900)

# Security headers (solo en producción)
if not DEBUG:
    SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    X_FRAME_OPTIONS = "DENY"
    SECURE_HSTS_SECONDS = 31536000  # 1 año
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_REFERRER_POLICY = "same-origin"

# Celery
CELERY_BROKER_URL = f"redis://{env('REDIS_HOST', default='redis')}:6379/0"
CELERY_RESULT_BACKEND = f"redis://{env('REDIS_HOST', default='redis')}:6379/0"

# Caching con Redis (o LocMem en dev sin Redis)
REDIS_HOST = env("REDIS_HOST", default="redis")
USE_REDIS = not env.bool("USE_SQLITE", default=False)
if USE_REDIS:
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
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "todolist-dev",
        }
    }

# Channels (WebSocket)
ASGI_APPLICATION = "config.asgi.application"
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer" if USE_REDIS else "channels.layers.InMemoryChannelLayer",
        "CONFIG": {"hosts": [(REDIS_HOST, 6379)]} if USE_REDIS else {},
    },
}

# GraphQL
GRAPHENE = {
    "SCHEMA": "apps.graphql_app.schema.schema",
    "MIDDLEWARE": ["apps.graphql_app.schema.DepthLimitMiddleware"],
}

# Allauth (social login)
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
SOCIALACCOUNT_ADAPTER = "apps.social_auth.adapters.CustomSocialAccountAdapter"
ACCOUNT_EMAIL_VERIFICATION = "none"

# Email (password reset y notificaciones). En dev, console backend.
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "25"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "false").lower() == "true"
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "no-reply@todolist.local")
# Una sola URL pública del frontend: FRONTEND_URL explícita tiene prioridad;
# si no, cae a DJANGO_FRONTEND_URL (misma var que CORS y redirects OAuth).
FRONTEND_URL = os.getenv("FRONTEND_URL") or DJANGO_FRONTEND_URL
# Opt-in del servidor para notificaciones por email (asignación, mención,
# recordatorio). Requiere además email_enabled en la preferencia del
# usuario. Desactivado por defecto: en dev el backend es console.
EMAIL_NOTIFICATIONS_ENABLED = env.bool("EMAIL_NOTIFICATIONS_ENABLED", default=False)

# Logging a consola (stdout) — docker/k8s lo recogen del stream.
# Sin este bloque Django solo loguea errores de request en producción
# y los warnings de negocio (blacklist JWT, automatizaciones, SSRF
# denegado) nunca llegaban a ningún lado.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {
            "format": "{levelname} {asctime} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": env("DJANGO_LOG_LEVEL", default="INFO" if not DEBUG else "DEBUG"),
    },
    "loggers": {
        # El torrente INFO de django.server (cada request) solo molesta.
        "django.server": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}

# Caducidad del token de reset de contraseña (segundos)
PASSWORD_RESET_TIMEOUT = 3600
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "username*", "password1*", "password2*"]
SOCIALACCOUNT_STORE_TOKENS = True
SOCIALACCOUNT_AUTO_SIGNUP = True

# El frontend enlaza directamente a la URL de login con GET; sin esto
# allauth muestra una página intermedia de confirmación.
SOCIALACCOUNT_LOGIN_ON_GET = True
# Tras el callback del IdP, allauth redirige aquí: el endpoint emite las
# cookies JWT y redirige de vuelta a la app (next=/app).
LOGIN_REDIRECT_URL = "/api/auth/social/jwt/?next=/app"

# Google OAuth
SOCIALACCOUNT_PROVIDERS: dict[str, dict] = {
    "google": {
        "APP": {
            "client_id": env("GOOGLE_OAUTH_CLIENT_ID", default=""),
            "secret": env("GOOGLE_OAUTH_CLIENT_SECRET", default=""),
            "key": "",
        },
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
    },
    "github": {
        "APP": {
            "client_id": env("GITHUB_OAUTH_CLIENT_ID", default=""),
            "secret": env("GITHUB_OAUTH_CLIENT_SECRET", default=""),
            "key": "",
        },
        "SCOPE": ["user:email", "repo"],
    },
}

# Enterprise SSO vía OpenID Connect (Keycloak, EntraID, Okta...).
# Deshabilitado por defecto: basta definir OIDC_ISSUER para registrar el
# provider con nombre en allauth (SOCIALACCOUNT_PROVIDERS[...]["APPS"]).
OIDC_ISSUER = env("OIDC_ISSUER", default="")
OIDC_PROVIDER_ID = env("OIDC_PROVIDER_ID", default="oidc")
OIDC_DISPLAY_NAME = env("OIDC_DISPLAY_NAME", default="SSO")
if OIDC_ISSUER:
    INSTALLED_APPS += ["allauth.socialaccount.providers.openid_connect"]
    SOCIALACCOUNT_PROVIDERS["openid_connect"] = {
        "APPS": [
            {
                "provider_id": OIDC_PROVIDER_ID,
                "name": OIDC_DISPLAY_NAME,
                "client_id": env("OIDC_CLIENT_ID", default=""),
                "secret": env("OIDC_CLIENT_SECRET", default=""),
                "settings": {"server_url": OIDC_ISSUER},
            }
        ]
    }

# Enterprise SSO vía SAML 2.0 (Entra ID, Okta, ADFS…). Requiere
# python3-saml (xmlsec) — dependencia opcional: solo se registra si el
# IdP está configurado (SAML_IDP_SSO_URL + SAML_IDP_X509CERT).
SAML_IDP_SSO_URL = env("SAML_IDP_SSO_URL", default="")
if SAML_IDP_SSO_URL:
    INSTALLED_APPS += ["allauth.socialaccount.providers.saml"]
    SAML_PROVIDER_ID = env("SAML_PROVIDER_ID", default="saml")
    SOCIALACCOUNT_PROVIDERS["saml"] = {
        "APPS": [
            {
                "provider_id": SAML_PROVIDER_ID,
                "name": env("SAML_DISPLAY_NAME", default="SAML SSO"),
                "settings": {
                    "idp": {
                        "entity_id": env("SAML_IDP_ENTITY_ID", default=""),
                        "sso_url": SAML_IDP_SSO_URL,
                        "slo_url": env("SAML_IDP_SLO_URL", default=""),
                        "x509cert": env("SAML_IDP_X509CERT", default=""),
                    },
                    "advanced": {
                        "allow_repeat_attribute_name": True,
                    },
                },
            }
        ]
    }

# Provisión SCIM 2.0 (Users↔User, Groups↔Organization). Solo se monta
# si SCIM_ENABLED=1 y hay al menos un bearer token (SCIM_BEARER_TOKENS,
# separados por coma para rotación sin corte).
SCIM_ENABLED = env.bool("SCIM_ENABLED", default=False)
SCIM_TOKENS = [
    t.strip() for t in env("SCIM_BEARER_TOKENS", default="").split(",")
    if t.strip()
]
if SCIM_ENABLED and SCIM_TOKENS:
    INSTALLED_APPS += ["apps.scim", "django_scim"]
    MIDDLEWARE += ["apps.scim.middleware.SCIMBearerAuthMiddleware"]
    SCIM_SERVICE_PROVIDER = {
        "NETLOC": env("SCIM_NETLOC", default=env("DJANGO_BACKEND_HOST", default="localhost:8000")),
        "SCHEME": env("SCIM_SCHEME", default="https"),
        "USER_ADAPTER": "apps.scim.adapters.SCIMUserAdapter",
        "GROUP_MODEL": "apps.collaboration.models.Organization",
        "GROUP_ADAPTER": "apps.scim.adapters.SCIMOrganizationAdapter",
        "WWW_AUTHENTICATE_HEADER": 'Bearer realm="scim"',
        "AUTHENTICATION_SCHEMES": [
            {
                "type": "oauthbearertoken",
                "name": "OAuth Bearer Token",
                "description": "Token estático SCIM (SCIM_BEARER_TOKENS)",
                "specUri": "https://www.rfc-editor.org/rfc/rfc6750",
            }
        ],
    }
else:
    SCIM_ENABLED = False

# Feature flags: defaults cuando no hay fila FeatureFlag en BD (el flag
# de BD gobierna cuando existe — is_enabled cae aquí solo si falta).
# Default True para features ya implementadas: el flag actúa como
# kill-switch / rollout gradual, no como activación de algo inexistente.
FEATURE_FLAGS = {
    "ai_assistant": env.bool("FEATURE_AI_ASSISTANT", default=True),
    "offline_sync": env.bool("FEATURE_OFFLINE_SYNC", default=True),
    "e2e_encryption": env.bool("FEATURE_E2E_ENCRYPTION", default=True),
}

# Sentry (opcional)
SENTRY_DSN = env("SENTRY_DSN", default="")

# Prometheus metrics
PROMETHEUS_METRICS_PORT = env.int("PROMETHEUS_METRICS_PORT", default=9090)
METRICS_TOKEN = env("METRICS_TOKEN", default="")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

from celery.schedules import crontab

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
    "sync-github-repos-data": {
        "task": "apps.integrations.tasks.sync_all_github_repos_data",
        "schedule": 900.0,  # cada 15 minutos
    },
    "daily-automation-check": {
        "task": "apps.automations.tasks.run_daily_checks_task",
        "schedule": 3600.0,  # cada hora
    },
    "daily-recurring-tasks": {
        "task": "apps.tasks.tasks.generate_recurring_tasks",
        "schedule": crontab(hour=6, minute=0),  # diario a las 6:00 AM
    },
    "send-due-reminders": {
        "task": "apps.tasks.tasks.send_due_reminders",
        "schedule": 60.0,  # cada minuto
    },
    "process-outbox": {
        "task": "apps.events.tasks.process_outbox_events",
        "schedule": 30.0,  # cada 30s
    },
    "daily-notification-digest": {
        "task": "apps.notifications.tasks.send_daily_digests",
        "schedule": crontab(hour=8, minute=0),  # diario a las 8:00 AM
    },
    "weekly-notification-digest": {
        "task": "apps.notifications.tasks.send_weekly_digests",
        # lunes a las 8:00 — resumen de la semana anterior
        "schedule": crontab(day_of_week=1, hour=8, minute=0),
    },
    "sync-external-calendars": {
        "task": "apps.collaboration.tasks.sync_external_calendars",
        "schedule": 900.0,  # cada 15 minutos
    },
}

# GitHub App
GITHUB_APP_ID = env("GITHUB_APP_ID")
GITHUB_APP_PRIVATE_KEY = env("GITHUB_APP_PRIVATE_KEY")
GITHUB_APP_CLIENT_ID = env("GITHUB_APP_CLIENT_ID")
GITHUB_APP_CLIENT_SECRET = env("GITHUB_APP_CLIENT_SECRET")
GITHUB_APP_WEBHOOK_SECRET = env("GITHUB_APP_WEBHOOK_SECRET")
GITHUB_APP_NAME = env("GITHUB_APP_NAME")

# Web Push (VAPID). Sin VAPID_PRIVATE_KEY el envío push es no-op.
VAPID_PUBLIC_KEY = env("VAPID_PUBLIC_KEY")
VAPID_PRIVATE_KEY = env("VAPID_PRIVATE_KEY")
VAPID_CLAIMS_SUBJECT = env("VAPID_CLAIMS_SUBJECT")

# LLM opcional del asistente de IA (BYOK, OpenAI-compatible).
# Sin AI_LLM_BASE_URL + AI_LLM_MODEL el asistente usa solo heurísticas.
# Ejemplos: OpenAI https://api.openai.com/v1 · Ollama http://localhost:11434/v1
AI_LLM_BASE_URL = env("AI_LLM_BASE_URL", default="")
AI_LLM_API_KEY = env("AI_LLM_API_KEY", default="")
AI_LLM_MODEL = env("AI_LLM_MODEL", default="")

# Jitsi Meet (videoconferencia integrada en reuniones).
# Servidor público gratuito por defecto; self-hosting: apuntar a tu instancia.
JITSI_BASE_URL = env("JITSI_BASE_URL", default="https://meet.jit.si")
