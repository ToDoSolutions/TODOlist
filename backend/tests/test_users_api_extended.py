"""Tests exhaustivos para users/api_auth.py y api_views.py."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient, APIRequestFactory

from apps.users.api_auth import APIKeyAuthentication, has_scope
from apps.users.models import APIKey

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="api", email="api@api.com", password="pass")


@pytest.fixture
def api_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
class TestAPIKeyAuthentication:
    def test_no_header(self):
        factory = APIRequestFactory()
        request = factory.get("/")
        auth = APIKeyAuthentication()
        assert auth.authenticate(request) is None

    def test_wrong_scheme(self):
        factory = APIRequestFactory()
        request = factory.get("/", HTTP_AUTHORIZATION="Bearer abc")
        auth = APIKeyAuthentication()
        assert auth.authenticate(request) is None

    def test_invalid_format(self):
        factory = APIRequestFactory()
        request = factory.get("/", HTTP_AUTHORIZATION="ApiKey")
        auth = APIKeyAuthentication()
        from rest_framework.exceptions import AuthenticationFailed
        with pytest.raises(AuthenticationFailed):
            auth.authenticate(request)

    def test_valid_key(self, user):
        raw, hashed, prefix = APIKey.generate_key()
        api_key = APIKey.objects.create(
            user=user, name="Test", key_prefix=prefix, hashed_key=hashed
        )
        factory = APIRequestFactory()
        request = factory.get("/", HTTP_AUTHORIZATION=f"ApiKey {raw}")
        auth = APIKeyAuthentication()
        result = auth.authenticate(request)
        assert result[0] == user
        assert result[1] == api_key

    def test_invalid_key(self):
        factory = APIRequestFactory()
        request = factory.get("/", HTTP_AUTHORIZATION="ApiKey invalid")
        auth = APIKeyAuthentication()
        from rest_framework.exceptions import AuthenticationFailed
        with pytest.raises(AuthenticationFailed):
            auth.authenticate(request)


@pytest.mark.django_db
class TestHasScope:
    def test_no_api_key(self):
        """JWT auth (no API key) tiene acceso total."""
        assert has_scope(None, "read") is True
        assert has_scope(None, "write") is True
        assert has_scope(None, "admin") is True

    def test_read_scope(self, user):
        api_key = APIKey.objects.create(
            user=user, name="Test", key_prefix="x", hashed_key="h",
            scopes=["read"]
        )
        assert has_scope(api_key, "read") is True
        assert has_scope(api_key, "write") is False

    def test_admin_scope(self, user):
        api_key = APIKey.objects.create(
            user=user, name="Test", key_prefix="x", hashed_key="h",
            scopes=["admin"]
        )
        assert has_scope(api_key, "read") is True
        assert has_scope(api_key, "write") is True
        assert has_scope(api_key, "admin") is True


@pytest.mark.django_db
class TestAPIKeyViewSet:
    def test_list(self, api_client, user):
        APIKey.objects.create(user=user, name="Key1", key_prefix="x", hashed_key="h1")
        response = api_client.get("/api/api-keys/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1

    def test_create(self, api_client, user):
        response = api_client.post("/api/api-keys/", {
            "name": "My Key", "scopes": ["read", "write"]
        }, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert "key" in response.data
        assert response.data["key"].startswith("tl_")
        assert APIKey.objects.filter(user=user, name="My Key").exists()

    def test_create_default_scopes(self, api_client, user):
        response = api_client.post("/api/api-keys/", {"name": "My Key"}, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        api_key = APIKey.objects.get(user=user)
        # El serializer aplica default [] si no se envían scopes
        assert api_key.scopes == []

    def test_revoke(self, api_client, user):
        api_key = APIKey.objects.create(user=user, name="Key1", key_prefix="x", hashed_key="h1")
        response = api_client.post(f"/api/api-keys/{api_key.id}/revoke/")
        assert response.status_code == status.HTTP_200_OK
        api_key.refresh_from_db()
        assert api_key.is_active is False

    def test_revoke_other_user(self, api_client):
        """Verifica que no se puede revocar la API key de otro usuario."""
        other = User.objects.create_user(username="other", email="o@o.com", password="pass")
        api_key = APIKey.objects.create(user=other, name="Key1", key_prefix="x", hashed_key="h1")
        response = api_client.post(f"/api/api-keys/{api_key.id}/revoke/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_list_filters_by_user(self, api_client):
        """Verifica que solo lista las API keys del usuario."""
        other = User.objects.create_user(username="other", email="o@o.com", password="pass")
        APIKey.objects.create(user=other, name="Key1", key_prefix="x", hashed_key="h1")
        response = api_client.get("/api/api-keys/")
        assert len(response.data) == 0


@pytest.mark.django_db
class TestUserMeView:
    def test_me(self, api_client, user):
        response = api_client.get("/api/users/me/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["email"] == user.email
        assert response.data["username"] == user.username

    def test_deactivate(self, api_client, user):
        response = api_client.post("/api/users/me/deactivate/", {"password": "pass"})
        assert response.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.is_active is False

    def test_delete_account_requires_confirm(self, api_client, user):
        response = api_client.delete("/api/users/me/delete_account/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert User.objects.filter(id=user.id).exists()

    def test_delete_account(self, api_client, user):
        response = api_client.delete("/api/users/me/delete_account/?confirm=true", {"password": "pass"})
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not User.objects.filter(id=user.id).exists()
