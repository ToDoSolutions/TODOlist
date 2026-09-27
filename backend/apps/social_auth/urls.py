"""URLs para social auth con django-allauth."""
from django.urls import include, path

from .views import social_jwt_callback, sso_providers

urlpatterns = [
    path("auth/social/", include("allauth.urls")),
    path("auth/social/jwt/", social_jwt_callback, name="social-jwt-callback"),
    path("sso/providers/", sso_providers, name="sso-providers"),
]
