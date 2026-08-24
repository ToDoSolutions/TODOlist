"""URLs para API keys."""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api_views import APIKeyViewSet

router = DefaultRouter()
router.register(r"api-keys", APIKeyViewSet, basename="api-key")

urlpatterns = [
    path("", include(router.urls)),
]
