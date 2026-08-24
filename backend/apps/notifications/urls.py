"""URLs para notificaciones."""
from rest_framework.routers import DefaultRouter
from django.urls import path, include

from .views import NotificationViewSet, NotificationPreferenceViewSet

router = DefaultRouter()
router.register(r"notifications", NotificationViewSet, basename="notification")
router.register(
    r"notification-preferences",
    NotificationPreferenceViewSet,
    basename="notification-preference",
)

urlpatterns = [
    path("", include(router.urls)),
]
