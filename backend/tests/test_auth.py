"""Tests de autenticación: registro, login, me."""
import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestRegister:
    def test_registro_exitoso(self, api_client):
        resp = api_client.post("/api/auth/register/", {
            "email": "nuevo@test.com",
            "username": "nuevo",
            "password": "Test12345!",
            "password2": "Test12345!",
        }, format="json")
        assert resp.status_code == 201
        assert resp.data["email"] == "nuevo@test.com"
        assert User.objects.filter(email="nuevo@test.com").exists()

    def test_registro_email_duplicado(self, api_client, user):
        resp = api_client.post("/api/auth/register/", {
            "email": "user@test.com",
            "username": "otro",
            "password": "Test12345!",
            "password2": "Test12345!",
        }, format="json")
        assert resp.status_code == 400

    def test_registro_password_no_coincide(self, api_client):
        resp = api_client.post("/api/auth/register/", {
            "email": "nuevo@test.com",
            "username": "nuevo",
            "password": "Test12345!",
            "password2": "OtraClave99!",
        }, format="json")
        assert resp.status_code == 400


@pytest.mark.django_db
class TestLogin:
    def test_login_exitoso(self, api_client, user):
        resp = api_client.post("/api/auth/login/", {
            "email": "user@test.com",
            "password": "testpass123",
        }, format="json")
        assert resp.status_code == 200
        assert "access" in resp.data
        assert "refresh" in resp.data

    def test_login_password_incorrecta(self, api_client, user):
        resp = api_client.post("/api/auth/login/", {
            "email": "user@test.com",
            "password": "incorrecta",
        }, format="json")
        assert resp.status_code == 401

    def test_login_usuario_inexistente(self, api_client):
        resp = api_client.post("/api/auth/login/", {
            "email": "nadie@test.com",
            "password": "testpass123",
        }, format="json")
        assert resp.status_code == 401


@pytest.mark.django_db
class TestMe:
    def test_obtener_perfil(self, authed_client, user):
        resp = authed_client.get("/api/auth/me/")
        assert resp.status_code == 200
        assert resp.data["email"] == "user@test.com"
        assert resp.data["username"] == "user"

    def test_perfil_sin_auth(self, api_client):
        resp = api_client.get("/api/auth/me/")
        assert resp.status_code == 401

    def test_actualizar_perfil(self, authed_client):
        resp = authed_client.patch("/api/auth/me/", {
            "username": "nuevo_nombre",
            "locale": "en",
        }, format="json")
        assert resp.status_code == 200
        assert resp.data["username"] == "nuevo_nombre"
        assert resp.data["locale"] == "en"
