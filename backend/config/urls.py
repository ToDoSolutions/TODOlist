"""URL configuration for TODOlist backend."""
from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)
from graphene_django.views import GraphQLView

from apps.users.views import RegisterView, MeView

urlpatterns = [
    path("admin/", admin.site.urls),

    # Auth
    path("api/auth/login/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/auth/register/", RegisterView.as_view(), name="auth_register"),
    path("api/auth/me/", MeView.as_view(), name="auth_me"),

    # API Keys
    path("api/", include("apps.users.api_urls")),

    # Resources
    path("api/", include("apps.projects.urls")),
    path("api/", include("apps.tasks.urls")),
    path("api/", include("apps.tags.urls")),

    # Integraciones (GitHub)
    path("api/", include("apps.integrations.urls")),
    path("api/", include("apps.notifications.urls")),
    path("api/", include("apps.automations.urls")),
    path("api/", include("apps.collaboration.urls")),

    # OpenAPI docs
    path("api/schema/", SpectacularAPIView.as_view(), name="api_schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="api_schema"), name="api_docs"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="api_schema"), name="api_redoc"),

    # GraphQL
    path("graphql/", GraphQLView.as_view(graphiql=True), name="graphql"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
