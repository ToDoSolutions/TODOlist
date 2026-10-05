"""Tests de regresión — Fase 1 de la auditoría (seguridad).

Cubre: SSRF por redirects en sync de calendarios externos (B-03),
enumeración de usuarios + case-sensitivity en encryption (B-18),
throttle de github_oauth_start (B-20), carrera en register_device
(B-25) y resiliencia/log de _revoke_all_tokens (B-15).
"""
from unittest.mock import MagicMock, patch

import pytest
from django.db import IntegrityError
from rest_framework.throttling import AnonRateThrottle

from apps.encryption.models import UserPublicKey


# --- B-03: SSRF redirect en sync de calendarios ---

@pytest.mark.django_db
class TestCalendarSyncSSRF:
    def test_sync_no_sigue_redirects(self, user):
        """Una URL validada que responde 30x a un destino interno no
        debe seguirse: requests.get va con allow_redirects=False."""
        from apps.collaboration.models import ExternalCalendar
        from apps.collaboration.tasks import sync_external_calendar

        cal = ExternalCalendar.objects.create(
            user=user, name="ext", url="https://feed.example.com/cal.ics",
        )
        resp = MagicMock()
        resp.status_code = 302
        resp.content = b""
        resp.raise_for_status = lambda: None
        with patch("apps.collaboration.tasks._is_safe_url",
                   return_value=True), patch(
                "apps.collaboration.tasks.requests.get",
                return_value=resp) as mock_get:
            sync_external_calendar(cal)
        assert mock_get.call_args.kwargs.get("allow_redirects") is False

    def test_sync_302_no_importa_eventos(self, user):
        """Con redirects deshabilitados el body del 302 no es un feed
        válido → sync falla limpio, sin seguir el destino."""
        from apps.collaboration.models import (
            ExternalCalendar,
            ExternalEvent,
        )
        from apps.collaboration.tasks import sync_external_calendar

        cal = ExternalCalendar.objects.create(
            user=user, name="ext", url="https://feed.example.com/cal.ics",
        )
        resp = MagicMock()
        resp.status_code = 302
        resp.content = b"<html>redirect</html>"
        resp.raise_for_status = lambda: None
        with patch("apps.collaboration.tasks._is_safe_url",
                   return_value=True), patch(
                "apps.collaboration.tasks.requests.get",
                return_value=resp):
            result = sync_external_calendar(cal)
        assert result is None
        assert not ExternalEvent.objects.filter(calendar=cal).exists()
        cal.refresh_from_db()
        assert cal.last_error


# --- B-18: enumeración en lookup + case en share ---

@pytest.mark.django_db
class TestPublicKeyLookup:
    def test_lookup_no_distingue_usuario_inexistente(
        self, authed_client, other_user
    ):
        """404 idéntico para email no registrado y para registrado sin
        clave activa — no se puede enumerar."""
        r1 = authed_client.get(
            "/api/public-keys/lookup/?email=noexiste@x.com")
        r2 = authed_client.get(
            f"/api/public-keys/lookup/?email={other_user.email}")
        assert r1.status_code == 404
        assert r2.status_code == 404
        assert r1.data == r2.data

    def test_lookup_case_insensitive(self, authed_client, other_user):
        UserPublicKey.objects.create(
            user=other_user, public_key="pk", key_id="k1",
            is_active=True,
        )
        resp = authed_client.get(
            f"/api/public-keys/lookup/?email={other_user.email.upper()}")
        assert resp.status_code == 200

    def test_share_case_insensitive(self, authed_client, user,
                                    other_user, task):
        """share con email en distinto case debe encontrar al usuario."""
        from apps.encryption.models import (
            EncryptedKeyShare,
            EncryptedTask,
        )

        key = UserPublicKey.objects.create(
            user=other_user, public_key="pk", key_id="k1",
            is_active=True,
        )
        et = EncryptedTask.objects.create(
            owner=user, task=task, encrypted_data="d",
            encryption_key_id="k1", iv="i", auth_tag="t",
            algorithm="AES-GCM",
        )
        resp = authed_client.post(
            f"/api/encrypted-tasks/{et.id}/share/", {
                "user_email": other_user.email.upper(),
                "encrypted_key": "EK",
                "public_key_id": key.id,
            }, format="json")
        assert resp.status_code == 201
        assert EncryptedKeyShare.objects.filter(
            encrypted_task=et, user=other_user).exists()


# --- B-20: throttle en github_oauth_start ---

class TestGithubOauthThrottle:
    def test_oauth_start_tiene_throttle(self):
        from apps.integrations.views import github_oauth_start
        assert AnonRateThrottle in (
            github_oauth_start.cls.throttle_classes)


# --- B-25: carrera en register_device ---

@pytest.mark.django_db
class TestRegisterDeviceRace:
    def test_integrity_error_devuelve_existente(self, user):
        """Si el create pierde la carrera (IntegrityError por unique),
        el dispositivo existente se devuelve en vez de propagar 500."""
        from apps.offline_sync.models import SyncDevice
        from apps.offline_sync.services import register_device

        existing = SyncDevice.objects.create(
            user=user, device_id="dev-race", device_name="old")
        with patch.object(
            SyncDevice.objects, "get_or_create",
            side_effect=IntegrityError("dup"),
        ):
            device = register_device(user, "dev-race", "nuevo")
        assert device.pk == existing.pk
        assert device.device_name == "nuevo"

    def test_integrity_error_otro_usuario_403(self, user, other_user):
        from django.core.exceptions import PermissionDenied

        from apps.offline_sync.models import SyncDevice
        from apps.offline_sync.services import register_device

        SyncDevice.objects.create(user=other_user, device_id="dev-x")
        with patch.object(
            SyncDevice.objects, "get_or_create",
            side_effect=IntegrityError("dup"),
        ), pytest.raises(PermissionDenied):
            register_device(user, "dev-x", "robo")


# --- B-15: _revoke_all_tokens ---

@pytest.mark.django_db
class TestRevokeAllTokens:
    def test_fallo_blacklist_no_propaga_y_loggea(self, user, caplog):
        """Un fallo real del blacklist (no ImportError) debe loggearse
        en warning — los refresh tokens antiguos quedan válidos."""
        from apps.users.views import _revoke_all_tokens

        with caplog.at_level("WARNING"), patch(
            "rest_framework_simplejwt.token_blacklist.models."
            "OutstandingToken.objects.filter",
            side_effect=RuntimeError("db down"),
        ):
            _revoke_all_tokens(user)
        assert any(
            "revoke tokens" in r.message.lower()
            for r in caplog.records if r.levelname == "WARNING"
        )
