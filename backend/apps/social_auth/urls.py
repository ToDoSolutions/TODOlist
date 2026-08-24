"""URLs para social auth con django-allauth."""
from django.urls import path, include
from allauth.socialaccount.views import signup
from .views import social_jwt_callback

urlpatterns = [
    path("auth/social/", include("allauth.urls")),
    path("auth/social/jwt/", social_jwt_callback, name="social-jwt-callback"),
]
