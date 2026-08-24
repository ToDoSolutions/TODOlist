"""URLs para API keys y 2FA."""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api_views import APIKeyViewSet
from .twofactor_views import twofactor_manage

router = DefaultRouter()
router.register(r"api-keys", APIKeyViewSet, basename="api-key")

urlpatterns = [
    path("", include(router.urls)),
    path("auth/2fa/", twofactor_manage, name="twofactor-manage"),
]
