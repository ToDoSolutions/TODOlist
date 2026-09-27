"""Tests de Fase 15: 2FA con TOTP y códigos de backup."""
import pyotp
import pytest

from apps.users.models import TwoFactorSecret


@pytest.mark.django_db
class TestTwoFactor:
    def test_setup_2fa(self, authed_client, user):
        """Iniciar setup de 2FA genera un secret y URI."""
        resp = authed_client.post("/api/auth/2fa/", {"action": "setup"}, format="json")
        assert resp.status_code == 200
        assert "secret" in resp.data
        assert "otpauth_uri" in resp.data
        assert resp.data["secret"]  # No vacío
        # Debe crear el registro
        assert TwoFactorSecret.objects.filter(user=user).exists()
        tf = user.twofactor
        assert tf.is_enabled is False  # Aún no confirmado

    def test_confirmar_2fa_codigo_valido(self, authed_client, user):
        """Confirmar 2FA con un código TOTP válido lo activa."""
        # Setup
        authed_client.post("/api/auth/2fa/", {"action": "setup"}, format="json")
        tf = user.twofactor
        # Generar código válido
        totp = pyotp.TOTP(tf.secret)
        code = totp.now()
        # Confirmar
        resp = authed_client.post("/api/auth/2fa/", {"action": "confirm", "code": code}, format="json")
        assert resp.status_code == 200
        assert "backup_codes" in resp.data
        assert len(resp.data["backup_codes"]) == 10
        tf.refresh_from_db()
        assert tf.is_enabled is True

    def test_confirmar_2fa_codigo_invalido(self, authed_client, user):
        """Confirmar con código inválido falla."""
        authed_client.post("/api/auth/2fa/", {"action": "setup"}, format="json")
        resp = authed_client.post("/api/auth/2fa/", {"action": "confirm", "code": "000000"}, format="json")
        assert resp.status_code == 400
        assert "error" in resp.data

    def test_get_estado_2fa(self, authed_client, user):
        """GET retorna el estado del 2FA."""
        resp = authed_client.get("/api/auth/2fa/")
        assert resp.status_code == 200
        assert resp.data["is_enabled"] is False

    def test_get_estado_2fa_activado(self, authed_client, user):
        """GET retorna is_enabled=True cuando está activado."""
        # Setup + confirm
        authed_client.post("/api/auth/2fa/", {"action": "setup"}, format="json")
        tf = user.twofactor
        totp = pyotp.TOTP(tf.secret)
        authed_client.post("/api/auth/2fa/", {"action": "confirm", "code": totp.now()}, format="json")
        resp = authed_client.get("/api/auth/2fa/")
        assert resp.status_code == 200
        assert resp.data["is_enabled"] is True

    def test_desactivar_2fa(self, authed_client, user):
        """Desactivar 2FA con código válido."""
        # Activar
        authed_client.post("/api/auth/2fa/", {"action": "setup"}, format="json")
        tf = user.twofactor
        totp = pyotp.TOTP(tf.secret)
        authed_client.post("/api/auth/2fa/", {"action": "confirm", "code": totp.now()}, format="json")
        # Desactivar
        code = totp.now()
        resp = authed_client.delete("/api/auth/2fa/", {"code": code}, format="json")
        assert resp.status_code == 200
        tf.refresh_from_db()
        assert tf.is_enabled is False

    def test_desactivar_2fa_codigo_invalido(self, authed_client, user):
        """Desactivar 2FA con código inválido falla."""
        authed_client.post("/api/auth/2fa/", {"action": "setup"}, format="json")
        tf = user.twofactor
        totp = pyotp.TOTP(tf.secret)
        authed_client.post("/api/auth/2fa/", {"action": "confirm", "code": totp.now()}, format="json")
        resp = authed_client.delete("/api/auth/2fa/", {"code": "000000"}, format="json")
        assert resp.status_code == 400

    def test_setup_sin_2fa_previo(self, authed_client, user):
        """Setup crea el registro si no existe."""
        assert not TwoFactorSecret.objects.filter(user=user).exists()
        resp = authed_client.post("/api/auth/2fa/", {"action": "setup"}, format="json")
        assert resp.status_code == 200
        assert TwoFactorSecret.objects.filter(user=user).exists()

    def test_confirmar_sin_setup_previo(self, authed_client, user):
        """Confirmar sin haber hecho setup falla."""
        resp = authed_client.post("/api/auth/2fa/", {"action": "confirm", "code": "123456"}, format="json")
        assert resp.status_code == 400
