"""URLs para notificaciones."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    NotificationPreferenceViewSet,
    NotificationViewSet,
    PushSubscriptionView,
    VapidPublicKeyView,
)

router = DefaultRouter()
router.register(r"notifications", NotificationViewSet, basename="notification")
router.register(
    r"notification-preferences",
    NotificationPreferenceViewSet,
    basename="notification-preference",
)

urlpatterns = [
    # Web Push (VAPID)
    path("push/vapid-key/", VapidPublicKeyView.as_view(), name="push-vapid-key"),
    path(
        "push/subscriptions/",
        PushSubscriptionView.as_view(),
        name="push-subscriptions",
    ),
    path("", include(router.urls)),
]
