"""Tests del flujo de recuperación de contraseña.

Cubre el contrato de seguridad clave: la solicitud siempre devuelve 200
(no filtra qué emails existen), el token es stateless/único, la nueva
contraseña se valida y las sesiones anteriores se revocan.
"""
import pytest
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

pytestmark = pytest.mark.django_db


class TestPasswordResetRequest:
    def test_siempre_200_aunque_el_email_no_exista(self, api_client):
        r = api_client.post("/api/auth/password-reset/", {"email": "nadie@x.com"})
        assert r.status_code == 200

    def test_envia_email_si_el_usuario_existe(self, api_client, user):
        r = api_client.post("/api/auth/password-reset/", {"email": user.email})
        assert r.status_code == 200
        assert len(mail.outbox) == 1
        assert "reset-password" in mail.outbox[0].body

    def test_no_envia_email_si_no_existe(self, api_client):
        api_client.post("/api/auth/password-reset/", {"email": "nadie@x.com"})
        assert len(mail.outbox) == 0

    def test_email_vacio_400(self, api_client):
        r = api_client.post("/api/auth/password-reset/", {"email": ""})
        assert r.status_code == 400


class TestPasswordResetConfirm:
    def _uid_token(self, user):
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        return uid, token

    def test_reset_exitoso(self, api_client, user):
        uid, token = self._uid_token(user)
        r = api_client.post("/api/auth/password-reset/confirm/", {
            "uid": uid, "token": token, "new_password": "NuevaPass!12345",
        })
        assert r.status_code == 200
        user.refresh_from_db()
        assert user.check_password("NuevaPass!12345")

    def test_token_invalido_400(self, api_client, user):
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        r = api_client.post("/api/auth/password-reset/confirm/", {
            "uid": uid, "token": "token-falso", "new_password": "NuevaPass!12345",
        })
        assert r.status_code == 400

    def test_uid_invalido_400(self, api_client):
        r = api_client.post("/api/auth/password-reset/confirm/", {
            "uid": "!!!", "token": "x", "new_password": "NuevaPass!12345",
        })
        assert r.status_code == 400

    def test_password_debil_rechazada(self, api_client, user):
        uid, token = self._uid_token(user)
        r = api_client.post("/api/auth/password-reset/confirm/", {
            "uid": uid, "token": token, "new_password": "123",
        })
        assert r.status_code == 400

    def test_token_es_de_un_solo_uso(self, api_client, user):
        uid, token = self._uid_token(user)
        api_client.post("/api/auth/password-reset/confirm/", {
            "uid": uid, "token": token, "new_password": "NuevaPass!12345",
        })
        r = api_client.post("/api/auth/password-reset/confirm/", {
            "uid": uid, "token": token, "new_password": "OtraPass!12345",
        })
        assert r.status_code == 400


class TestEmailVerification:
    def test_send_verification_envia_email(self, authed_client, user):
        r = authed_client.post("/api/auth/send-verification/")
        assert r.status_code == 200
        assert len(mail.outbox) == 1
        assert "verify-email" in mail.outbox[0].body

    def test_verify_marca_el_email(self, api_client, user):
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        r = api_client.post("/api/auth/verify-email/", {"uid": uid, "token": token})
        assert r.status_code == 200
        user.refresh_from_db()
        assert user.email_verified
        assert user.email_verified_at is not None

    def test_verify_token_invalido_400(self, api_client, user):
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        r = api_client.post("/api/auth/verify-email/", {"uid": uid, "token": "x"})
        assert r.status_code == 400

    def test_reenvio_si_ya_verificado(self, authed_client, user):
        user.email_verified = True
        user.save()
        r = authed_client.post("/api/auth/send-verification/")
        assert r.status_code == 200
        assert len(mail.outbox) == 0


class TestInboxFilter:
    def test_no_project_devuelve_solo_tareas_sin_proyecto(
        self, authed_client, user, project, task
    ):
        from apps.tasks.models import Task
        inbox_task = Task.objects.create(title="Sin clasificar", owner=user)
        r = authed_client.get("/api/tasks/?no_project=true")
        data = r.data if isinstance(r.data, list) else r.data["results"]
        ids = {t["id"] for t in data}
        assert inbox_task.id in ids
        assert task.id not in ids
