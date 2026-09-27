"""Tests exhaustivos para social_auth."""
from unittest.mock import MagicMock

import pytest
from django.contrib.auth import get_user_model
from django.test import RequestFactory

from apps.social_auth.adapters import CustomSocialAccountAdapter
from apps.social_auth.views import social_jwt_callback

User = get_user_model()


@pytest.mark.django_db
class TestCustomSocialAccountAdapter:
    def test_pre_social_login_verified_email(self):
        """Verifica que conecta cuentas si el email está verificado."""
        adapter = CustomSocialAccountAdapter()
        request = MagicMock()
        sociallogin = MagicMock()
        sociallogin.is_existing = False
        sociallogin.account.extra_data = {
            "email": "test@test.com",
            "email_verified": True,
        }
        user = User.objects.create_user(username="test", email="test@test.com", password="pass")
        adapter.pre_social_login(request, sociallogin)
        sociallogin.connect.assert_called_once_with(request, user)

    def test_pre_social_login_unverified_email(self):
        """Verifica que NO conecta cuentas si el email NO está verificado."""
        adapter = CustomSocialAccountAdapter()
        request = MagicMock()
        sociallogin = MagicMock()
        sociallogin.is_existing = False
        sociallogin.account.extra_data = {
            "email": "test@test.com",
            "email_verified": False,
        }
        User.objects.create_user(username="test", email="test@test.com", password="pass")
        adapter.pre_social_login(request, sociallogin)
        sociallogin.connect.assert_not_called()

    def test_pre_social_login_existing(self):
        """Verifica que no hace nada si la cuenta ya está conectada."""
        adapter = CustomSocialAccountAdapter()
        request = MagicMock()
        sociallogin = MagicMock()
        sociallogin.is_existing = True
        adapter.pre_social_login(request, sociallogin)
        sociallogin.connect.assert_not_called()

    def test_populate_user(self):
        """Verifica que populate_user rellena el usuario con datos del provider."""
        adapter = CustomSocialAccountAdapter()
        request = MagicMock()
        sociallogin = MagicMock()
        sociallogin.account.extra_data = {"name": "Test User", "email": "test@test.com"}
        data = {"email": "test@test.com"}
        user = adapter.populate_user(request, sociallogin, data)
        assert user.username == "Test User"


@pytest.mark.django_db
class TestSocialJwtCallback:
    def test_authenticated(self):
        """Verifica que retorna JWT si el usuario está autenticado."""
        import json
        user = User.objects.create_user(username="test", email="test@test.com", password="pass")
        factory = RequestFactory()
        request = factory.get("/social/jwt/")
        request.user = user
        response = social_jwt_callback(request)
        assert response.status_code == 200
        data = json.loads(response.content)
        assert "access" in data
        assert "refresh" in data

    def test_unauthenticated(self):
        """Verifica que retorna 401 si el usuario no está autenticado."""
        factory = RequestFactory()
        request = factory.get("/social/jwt/")
        request.user = MagicMock()
        request.user.is_authenticated = False
        response = social_jwt_callback(request)
        assert response.status_code == 401
