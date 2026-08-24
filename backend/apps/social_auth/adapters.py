"""Adapters para django-allauth con JWT."""
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Adapter para login social: conecta cuentas existentes por email."""

    def pre_social_login(self, request, sociallogin):
        """Conecta una cuenta social a un usuario existente si el email coincide."""
        from django.contrib.auth import get_user_model
        User = get_user_model()

        if sociallogin.is_existing:
            return  # Ya conectada

        email = sociallogin.account.extra_data.get("email")
        if email:
            try:
                user = User.objects.get(email=email)
                sociallogin.connect(request, user)
            except User.DoesNotExist:
                pass  # Se creará un usuario nuevo

    def populate_user(self, request, sociallogin, data):
        """Rellena el usuario con datos del provider social."""
        user = super().populate_user(request, sociallogin, data)
        extra = sociallogin.account.extra_data
        if "name" in extra and not user.username:
            user.username = extra.get("name", extra.get("login", user.email))
        return user
