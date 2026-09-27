"""Tests para users/security.py (lockout 2FA) y users/views.py (login 2FA, register, password)."""
import pyotp
import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.models import TwoFactorSecret
from apps.users.security import (
    TOTP_MAX_FAILURES,
    hash_backup_code,
    is_2fa_locked,
    record_2fa_failure,
    reset_2fa_failures,
)

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="sec", email="sec@sec.com", password="SecurePass123!"
    )


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
class TestTwoFactorLockout:
    def test_not_locked_initially(self, user):
        assert is_2fa_locked(user) is False

    def test_locked_after_max_failures(self, user):
        for _ in range(TOTP_MAX_FAILURES):
            record_2fa_failure(user)
        assert is_2fa_locked(user) is True

    def test_not_locked_below_max(self, user):
        for _ in range(TOTP_MAX_FAILURES - 1):
            record_2fa_failure(user)
        assert is_2fa_locked(user) is False

    def test_reset_clears_failures(self, user):
        for _ in range(TOTP_MAX_FAILURES):
            record_2fa_failure(user)
        assert is_2fa_locked(user) is True
        reset_2fa_failures(user)
        assert is_2fa_locked(user) is False

    def test_failures_isolated_per_user(self, user):
        other = User.objects.create_user(
            username="o2", email="o2@o.com", password="pass"
        )
        for _ in range(TOTP_MAX_FAILURES):
            record_2fa_failure(user)
        assert is_2fa_locked(user) is True
        assert is_2fa_locked(other) is False


@pytest.mark.django_db
class TestHashBackupCode:
    def test_hash_is_sha256(self):
        h = hash_backup_code("ABCD1234")
        assert len(h) == 64
        assert h == hash_backup_code("ABCD1234")

    def test_hash_normalizes(self):
        """Minúsculas y espacios producen el mismo hash."""
        assert hash_backup_code("abcd1234") == hash_backup_code("  ABCD1234  ")


@pytest.mark.django_db
class TestLogin2FA:
    """Tests del endpoint /api/auth/login/ con enforcement de 2FA."""

    def _login(self, client, user, **extra):
        data = {"email": user.email, "password": "SecurePass123!", **extra}
        return client.post("/api/auth/login/", data, format="json")

    def test_login_sin_2fa(self, api_client, user):
        resp = self._login(api_client, user)
        assert resp.status_code == status.HTTP_200_OK
        assert "access" in resp.data
        assert "refresh" in resp.data

    def test_login_2fa_sin_codigo(self, api_client, user):
        """Con 2FA activo y sin código → 400 requires_2fa."""
        secret = pyotp.random_base32()
        TwoFactorSecret.objects.create(user=user, secret=secret, is_enabled=True)
        resp = self._login(api_client, user)
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        # requires_2fa llega como flag en los errores de validación
        assert "requires_2fa" in resp.data

    def test_login_2fa_codigo_valido(self, api_client, user):
        secret = pyotp.random_base32()
        TwoFactorSecret.objects.create(user=user, secret=secret, is_enabled=True)
        code = pyotp.TOTP(secret).now()
        resp = self._login(api_client, user, totp_code=code)
        assert resp.status_code == status.HTTP_200_OK
        assert "access" in resp.data

    def test_login_2fa_codigo_invalido(self, api_client, user):
        secret = pyotp.random_base32()
        TwoFactorSecret.objects.create(user=user, secret=secret, is_enabled=True)
        resp = self._login(api_client, user, totp_code="000000")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_login_2fa_backup_code(self, api_client, user):
        secret = pyotp.random_base32()
        tf = TwoFactorSecret.objects.create(user=user, secret=secret, is_enabled=True)
        codes = tf.generate_backup_codes()
        resp = self._login(api_client, user, totp_code=codes[0])
        assert resp.status_code == status.HTTP_200_OK

    def test_login_2fa_lockout(self, api_client, user):
        """Tras N fallos el login se bloquea aunque el código sea válido."""
        secret = pyotp.random_base32()
        TwoFactorSecret.objects.create(user=user, secret=secret, is_enabled=True)
        for _ in range(TOTP_MAX_FAILURES):
            record_2fa_failure(user)
        code = pyotp.TOTP(secret).now()
        resp = self._login(api_client, user, totp_code=code)
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "Demasiados intentos" in str(resp.data)

    def test_login_2fa_disabled_no_code_needed(self, api_client, user):
        """2FA configurado pero no habilitado → login normal."""
        TwoFactorSecret.objects.create(
            user=user, secret=pyotp.random_base32(), is_enabled=False
        )
        resp = self._login(api_client, user)
        assert resp.status_code == status.HTTP_200_OK

    def test_login_password_incorrecta(self, api_client, user):
        resp = api_client.post(
            "/api/auth/login/",
            {"email": user.email, "password": "wrong"},
            format="json",
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_usuario_inactivo(self, api_client, user):
        user.is_active = False
        user.save()
        resp = self._login(api_client, user)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestRegister:
    def test_register_ok(self, api_client):
        resp = api_client.post("/api/auth/register/", {
            "email": "new@new.com",
            "username": "newuser",
            "password": "SecurePass123!",
            "password2": "SecurePass123!",
        }, format="json")
        assert resp.status_code == status.HTTP_201_CREATED
        u = User.objects.get(email="new@new.com")
        assert u.check_password("SecurePass123!")

    def test_register_passwords_no_coinciden(self, api_client):
        resp = api_client.post("/api/auth/register/", {
            "email": "new@new.com",
            "username": "newuser",
            "password": "SecurePass123!",
            "password2": "DifferentPass456!",
        }, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_email_duplicado(self, api_client, user):
        resp = api_client.post("/api/auth/register/", {
            "email": "sec@sec.com",
            "username": "otro",
            "password": "SecurePass123!",
            "password2": "SecurePass123!",
        }, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_email_case_insensitive(self, api_client, user):
        """Email duplicado con distinto case también se rechaza."""
        resp = api_client.post("/api/auth/register/", {
            "email": "SEC@SEC.COM",
            "username": "otro",
            "password": "SecurePass123!",
            "password2": "SecurePass123!",
        }, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_password_debil(self, api_client, settings):
        settings.AUTH_PASSWORD_VALIDATORS = [
            {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
             "OPTIONS": {"min_length": 8}},
        ]
        resp = api_client.post("/api/auth/register/", {
            "email": "new@new.com",
            "username": "newuser",
            "password": "123",
            "password2": "123",
        }, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_password_no_en_respuesta(self, api_client):
        """La contraseña nunca aparece en la respuesta."""
        resp = api_client.post("/api/auth/register/", {
            "email": "new@new.com",
            "username": "newuser",
            "password": "SecurePass123!",
            "password2": "SecurePass123!",
        }, format="json")
        assert resp.status_code == status.HTTP_201_CREATED
        assert "password" not in resp.data


@pytest.mark.django_db
class TestChangePassword:
    def _auth(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def test_change_password_ok(self, user):
        client = self._auth(user)
        resp = client.post("/api/auth/change-password/", {
            "current_password": "SecurePass123!",
            "new_password": "NewSecure456!",
        }, format="json")
        assert resp.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.check_password("NewSecure456!")

    def test_change_password_wrong_current(self, user):
        client = self._auth(user)
        resp = client.post("/api/auth/change-password/", {
            "current_password": "wrong",
            "new_password": "NewSecure456!",
        }, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        user.refresh_from_db()
        assert user.check_password("SecurePass123!")

    def test_change_password_missing_fields(self, user):
        client = self._auth(user)
        resp = client.post("/api/auth/change-password/", {}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_change_password_debil(self, user, settings):
        settings.AUTH_PASSWORD_VALIDATORS = [
            {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
             "OPTIONS": {"min_length": 8}},
        ]
        client = self._auth(user)
        resp = client.post("/api/auth/change-password/", {
            "current_password": "SecurePass123!",
            "new_password": "123",
        }, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestMeView:
    def test_me_get(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.get("/api/auth/me/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["email"] == user.email

    def test_me_update_timezone(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.patch("/api/auth/me/", {"timezone": "Europe/Madrid"}, format="json")
        assert resp.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.timezone == "Europe/Madrid"

    def test_me_email_readonly(self, user):
        """El email no se puede cambiar vía /me (read_only)."""
        client = APIClient()
        client.force_authenticate(user=user)
        client.patch("/api/auth/me/", {"email": "hacked@x.com"}, format="json")
        user.refresh_from_db()
        assert user.email == "sec@sec.com"
