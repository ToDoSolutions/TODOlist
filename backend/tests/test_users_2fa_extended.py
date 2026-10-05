"""Tests exhaustivos para users/twofactor_views.py y users/models.py."""
from datetime import timedelta

import pyotp
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.models import APIKey, TwoFactorSecret

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="2fa", email="2fa@2fa.com", password="pass")


@pytest.fixture
def api_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
class TestTwoFactorManage:
    def test_get_not_enabled(self, api_client):
        """Verifica que GET retorna disabled si no hay 2FA."""
        response = api_client.get("/api/auth/2fa/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_enabled"] is False

    def test_get_enabled(self, api_client, user):
        """Verifica que GET retorna enabled si 2FA está activo."""
        TwoFactorSecret.objects.create(user=user, secret="secret", is_enabled=True)
        response = api_client.get("/api/auth/2fa/")
        assert response.data["is_enabled"] is True

    def test_setup(self, api_client, user):
        """Verifica que POST setup genera secret y URI."""
        response = api_client.post("/api/auth/2fa/", {"action": "setup"})
        assert response.status_code == status.HTTP_200_OK
        assert "secret" in response.data
        assert "otpauth_uri" in response.data
        assert TwoFactorSecret.objects.filter(user=user).exists()

    def test_setup_regenerates(self, api_client, user):
        """Re-setup con 2FA activo exige el segundo factor (anti-bypass)."""
        secret = pyotp.random_base32()
        tf = TwoFactorSecret.objects.create(
            user=user, secret=secret, is_enabled=True
        )
        # Sin código → rechazado, y el 2FA sigue activo
        resp = api_client.post("/api/auth/2fa/", {"action": "setup"})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        tf.refresh_from_db()
        assert tf.secret == secret
        assert tf.is_enabled is True
        # Con TOTP válido → regenera el secret y desactiva hasta confirmar
        code = pyotp.TOTP(secret).now()
        resp = api_client.post(
            "/api/auth/2fa/", {"action": "setup", "code": code}
        )
        assert resp.status_code == status.HTTP_200_OK
        tf.refresh_from_db()
        assert tf.secret != secret
        assert tf.is_enabled is False

    def test_confirm_valid_code(self, api_client, user):
        """Verifica que confirm con código válido activa 2FA."""
        secret = pyotp.random_base32()
        tf = TwoFactorSecret.objects.create(user=user, secret=secret)
        totp = pyotp.TOTP(secret)
        code = totp.now()
        response = api_client.post("/api/auth/2fa/", {"action": "confirm", "code": code})
        assert response.status_code == status.HTTP_200_OK
        assert "backup_codes" in response.data
        tf.refresh_from_db()
        assert tf.is_enabled is True
        # Los códigos se muestran en claro al usuario pero se almacenan hasheados
        assert len(response.data["backup_codes"]) == 10
        assert len(tf.backup_codes) == 10
        # PBKDF2 con sal: formato "pbkdf2$<salt>$<digest>" (no reversible)
        assert all(h.startswith("pbkdf2$") for h in tf.backup_codes)

    def test_confirm_invalid_code(self, api_client, user):
        """Verifica que confirm con código inválido falla."""
        TwoFactorSecret.objects.create(user=user, secret=pyotp.random_base32())
        response = api_client.post("/api/auth/2fa/", {"action": "confirm", "code": "000000"})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_confirm_no_setup(self, api_client):
        """Verifica que confirm sin setup falla."""
        response = api_client.post("/api/auth/2fa/", {"action": "confirm", "code": "123456"})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "setup" in response.data["error"]

    def test_invalid_action(self, api_client):
        """Verifica que acción inválida retorna error."""
        response = api_client.post("/api/auth/2fa/", {"action": "invalid"})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_delete_with_totp(self, api_client, user):
        """Verifica que DELETE con TOTP válido desactiva 2FA."""
        secret = pyotp.random_base32()
        tf = TwoFactorSecret.objects.create(user=user, secret=secret, is_enabled=True)
        totp = pyotp.TOTP(secret)
        code = totp.now()
        response = api_client.delete("/api/auth/2fa/", {"code": code})
        assert response.status_code == status.HTTP_200_OK
        tf.refresh_from_db()
        assert tf.is_enabled is False

    def test_delete_with_backup_code(self, api_client, user):
        """Verifica que DELETE con backup code desactiva 2FA."""
        tf = TwoFactorSecret.objects.create(user=user, secret="secret", is_enabled=True)
        codes = tf.generate_backup_codes()
        response = api_client.delete("/api/auth/2fa/", {"code": codes[0]})
        assert response.status_code == status.HTTP_200_OK
        tf.refresh_from_db()
        assert tf.is_enabled is False
        assert tf.backup_codes == []

    def test_delete_invalid_code(self, api_client, user):
        """Verifica que DELETE con código inválido falla."""
        TwoFactorSecret.objects.create(user=user, secret="secret", is_enabled=True)
        response = api_client.delete("/api/auth/2fa/", {"code": "invalid"})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_delete_not_enabled(self, api_client):
        """Verifica que DELETE sin 2FA falla."""
        response = api_client.delete("/api/auth/2fa/", {"code": "123"})
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestAPIKey:
    def test_generate_key(self):
        """Verifica que generate_key retorna raw, hash y prefix."""
        raw, hashed, prefix = APIKey.generate_key()
        assert raw.startswith("tl_")
        assert len(raw) > 20
        assert len(hashed) == 64  # SHA256 hex
        assert prefix == raw[:12]

    def test_verify_key(self, user):
        """Verifica que verify_key retorna APIKey si es válida."""
        raw, hashed, prefix = APIKey.generate_key()
        api_key = APIKey.objects.create(
            user=user, name="Test", key_prefix=prefix, hashed_key=hashed
        )
        result = APIKey.verify_key(raw)
        assert result == api_key
        assert result.last_used_at is not None

    def test_verify_key_invalid(self):
        """Verifica que verify_key retorna None si no existe."""
        assert APIKey.verify_key("tl_invalid") is None
        assert APIKey.verify_key("not_tl_prefix") is None
        assert APIKey.verify_key("") is None

    def test_verify_key_expired(self, user):
        """Verifica que verify_key retorna None si está expirada."""
        raw, hashed, prefix = APIKey.generate_key()
        APIKey.objects.create(
            user=user, name="Test", key_prefix=prefix, hashed_key=hashed,
            expires_at=timezone.now() - timedelta(days=1)
        )
        assert APIKey.verify_key(raw) is None

    def test_verify_key_inactive(self, user):
        """Verifica que verify_key retorna None si está inactiva."""
        raw, hashed, prefix = APIKey.generate_key()
        APIKey.objects.create(
            user=user, name="Test", key_prefix=prefix, hashed_key=hashed,
            is_active=False
        )
        assert APIKey.verify_key(raw) is None


@pytest.mark.django_db
class TestTwoFactorSecret:
    def test_generate_backup_codes(self, user):
        """Verifica que generate_backup_codes genera 10 códigos de 16 chars."""
        tf = TwoFactorSecret.objects.create(user=user, secret="secret")
        codes = tf.generate_backup_codes()
        assert len(codes) == 10
        assert all(len(c) == 16 for c in codes)
        assert all(c.isupper() or c.isdigit() for c in "".join(codes))

    def test_use_backup_code(self, user):
        """Verifica que use_backup_code consume el código."""
        tf = TwoFactorSecret.objects.create(user=user, secret="secret")
        codes = tf.generate_backup_codes()
        first_code = codes[0]  # Guardar copia: codes es la misma lista que backup_codes
        assert tf.use_backup_code(first_code) is True
        tf.refresh_from_db()
        assert len(tf.backup_codes) == 9
        assert tf.use_backup_code(first_code) is False  # Ya usado

    def test_verify_totp(self, user):
        """Verifica que verify_totp valida códigos TOTP."""
        secret = pyotp.random_base32()
        tf = TwoFactorSecret.objects.create(user=user, secret=secret)
        totp = pyotp.TOTP(secret)
        assert tf.verify_totp(totp.now()) is True
        assert tf.verify_totp("000000") is False
