"""URLs para API keys, 2FA y gestión de cuenta."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .api_views import (
    APIKeyViewSet,
    UserMeView,
    inbound_email,
    logout_all_view,
    logout_view,
)
from .twofactor_views import twofactor_manage

router = DefaultRouter()
router.register(r"api-keys", APIKeyViewSet, basename="api-key")

user_me_view = UserMeView.as_view({
    "get": "me",
    "post": "deactivate",
    "patch": "update_profile",
    "put": "update_profile",
    "delete": "delete_account",
})

urlpatterns = [
    path("", include(router.urls)),
    path("auth/2fa/", twofactor_manage, name="twofactor-manage"),
    path("auth/logout/", logout_view, name="auth-logout"),
    path("auth/logout-all/", logout_all_view, name="auth-logout-all"),
    path("users/me/", user_me_view, name="user-me"),
    path("users/me/deactivate/", UserMeView.as_view({"post": "deactivate"}), name="user-deactivate"),
    path("users/me/delete_account/", UserMeView.as_view({"delete": "delete_account"}), name="user-delete"),
    path("users/me/calendar_token/", UserMeView.as_view({"post": "calendar_token", "delete": "calendar_token_revoke"}), name="calendar-token"),
    path("users/me/email_token/", UserMeView.as_view({"post": "email_token", "delete": "email_token_revoke"}), name="email-token"),
    path("inbound-email/", inbound_email, name="inbound-email"),
]
