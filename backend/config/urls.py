"""URL configuration for TODOlist backend."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from graphene_django.views import GraphQLView

from apps.users.views import (
    CookieTokenRefreshView,
    LoginView,
    MeView,
    RegisterView,
    change_password,
    password_reset_confirm,
    password_reset_request,
    send_verification_email,
    verify_email,
)

urlpatterns = [
    path("admin/", admin.site.urls),

    # Auth (login con enforcement de 2FA)
    path("api/auth/login/", LoginView.as_view(), name="token_obtain_pair"),
    path("api/auth/refresh/", CookieTokenRefreshView.as_view(), name="token_refresh"),
    path("api/auth/register/", RegisterView.as_view(), name="auth_register"),
    path("api/auth/me/", MeView.as_view(), name="auth_me"),
    path("api/auth/change-password/", change_password, name="change_password"),
    path("api/auth/password-reset/", password_reset_request, name="password_reset"),
    path("api/auth/password-reset/confirm/", password_reset_confirm, name="password_reset_confirm"),
    path("api/auth/send-verification/", send_verification_email, name="send_verification"),
    path("api/auth/verify-email/", verify_email, name="verify_email"),

    # API Keys
    path("api/", include("apps.users.api_urls")),

    # Social auth (Google, GitHub)
    path("api/", include("apps.social_auth.urls")),

    # OKRs
    path("api/", include("apps.okrs.urls")),

    # Feature flags
    path("api/", include("apps.feature_flags.urls")),

    # AI assistant
    path("api/", include("apps.ai_assistant.urls")),

    # Chat integrations (Slack, Discord)
    path("api/", include("apps.integrations_chat.urls")),

    # Monitoring (Prometheus metrics)
    path("api/", include("apps.monitoring.urls")),

    # Offline sync
    path("api/", include("apps.offline_sync.urls")),

    # Cifrado a nivel de aplicación (field-level encryption)
    path("api/", include("apps.encryption.urls")),

    # Resources
    path("api/", include("apps.projects.urls")),
    path("api/", include("apps.tasks.urls")),
    path("api/", include("apps.tags.urls")),

    # MCP server (JSON-RPC Streamable HTTP para agentes/LLMs)
    path("api/", include("apps.mcp.urls")),

    # CalDAV (clientes de tareas: Thunderbird, Tasks.org, Apple…)
    path("api/", include("apps.caldav.urls")),

    # Integraciones (GitHub)
    path("api/", include("apps.integrations.urls")),
    path("api/", include("apps.notifications.urls")),
    path("api/", include("apps.automations.urls")),
    path("api/", include("apps.collaboration.urls")),
    path("api/", include("apps.wiki.urls")),
    path("api/", include("apps.intake.urls")),
    path("api/", include("apps.dashboards.urls")),

    # OpenAPI docs
    path("api/schema/", SpectacularAPIView.as_view(), name="api_schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="api_schema"), name="api_docs"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="api_schema"), name="api_redoc"),

    # GraphQL (IDE/introspection solo en DEBUG)
    path("graphql/", GraphQLView.as_view(graphiql=settings.DEBUG), name="graphql"),
]

# SCIM 2.0 provisioning (IdP → usuarios/organizaciones). Siempre montado:
# sin SCIM_ENABLED/tokens válidos el middleware rechaza con 401.
urlpatterns += [path("scim/v2/", include("django_scim.urls"))]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
