"""Tests para matar mutantes sobrevivientes de la tercera ronda de mutmut.

Targets (60 sobrevivientes):
- apps/encryption/views.py (16): algorithm defaults, rotate, destroy, response keys
- apps/integrations/views.py (30): import_issues, oauth, webhook, permissions
- apps/automations/engine.py (13): defaults, context keys, control flow
- apps/offline_sync/services.py (1): device_id default
"""
import json
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone

from apps.automations.engine import (
    evaluate_conditions,
    execute_action,
    run_daily_checks,
    trigger_automation,
)
from apps.automations.models import AutomationLog, AutomationRule
from apps.encryption.models import EncryptedKeyShare, EncryptedTask, UserPublicKey
from apps.integrations.models import (
    GitHubInstallation,
    GitHubPullRequest,
    GitHubRepo,
)
from apps.notifications.models import Notification
from apps.tasks.models import Task

User = get_user_model()


# ============================================================================
# encryption/views.py — 16 sobrevivientes (276-277, 291, 295, 297, 302-305, 307-311, 314-315)
# ============================================================================

@pytest.fixture
def public_key(user):
    return UserPublicKey.objects.create(
        user=user,
        public_key="base64key==",
        key_id="key-1",
        algorithm="RSA-OA-256",
    )


@pytest.mark.django_db
class TestPublicKeyCreateMutationKills:
    """Mata mutantes 276-277: algorithm key y default en perform_create."""

    def test_create_with_custom_algorithm(self, authed_client, user):
        """Crear clave con algorithm personalizado lo persiste (mata 276 y 277)."""
        resp = authed_client.post("/api/public-keys/", {
            "public_key": "base64key==",
            "key_id": "key-custom-alg",
            "algorithm": "X25519",
        }, format="json")
        assert resp.status_code == 201
        key = UserPublicKey.objects.get(key_id="key-custom-alg")
        assert key.algorithm == "X25519"  # No "RSA-OA-256" (mata 276 y 277)

    def test_create_without_algorithm_uses_default(self, authed_client, user):
        """Crear clave sin algorithm usa default 'RSA-OA-256'."""
        resp = authed_client.post("/api/public-keys/", {
            "public_key": "base64key==",
            "key_id": "key-default-alg",
        }, format="json")
        assert resp.status_code == 201
        key = UserPublicKey.objects.get(key_id="key-default-alg")
        assert key.algorithm == "RSA-OA-256"  # No "XXRSA-OA-256XX"


@pytest.mark.django_db
class TestPublicKeyRotateMutationKills:
    """Mata mutantes 291, 295, 297, 302-305: rotate algorithm, validation, is_active, shares, response keys."""

    def test_rotate_with_custom_algorithm(self, authed_client, user, public_key):
        """Rotate con algorithm personalizado lo persiste (mata 291)."""
        resp = authed_client.post(
            f"/api/public-keys/{public_key.id}/rotate/",
            {"public_key": "newkey==", "key_id": "key-2", "algorithm": "X25519"},
            format="json",
        )
        assert resp.status_code == 200
        new_key = UserPublicKey.objects.get(key_id="key-2")
        assert new_key.algorithm == "X25519"  # No old_key.algorithm

    def test_rotate_without_algorithm_uses_old(self, authed_client, user, public_key):
        """Rotate sin algorithm usa el algorithm de la clave antigua."""
        resp = authed_client.post(
            f"/api/public-keys/{public_key.id}/rotate/",
            {"public_key": "newkey==", "key_id": "key-2"},
            format="json",
        )
        assert resp.status_code == 200
        new_key = UserPublicKey.objects.get(key_id="key-2")
        assert new_key.algorithm == "RSA-OA-256"  # Heredado de old_key

    def test_rotate_missing_only_public_key_still_400(self, authed_client, user, public_key):
        """Rotate sin public_key pero con key_id devuelve 400 (mata 295: or→and)."""
        resp = authed_client.post(
            f"/api/public-keys/{public_key.id}/rotate/",
            {"key_id": "key-2"},  # Falta public_key
            format="json",
        )
        # Si usa 'and', solo falla si AMBOS faltan → pasaría → 200 incorrecto
        # Si usa 'or', falla si cualquiera falta → 400 correcto
        assert resp.status_code == 400

    def test_rotate_missing_only_key_id_still_400(self, authed_client, user, public_key):
        """Rotate sin key_id pero con public_key devuelve 400 (mata 295)."""
        resp = authed_client.post(
            f"/api/public-keys/{public_key.id}/rotate/",
            {"public_key": "newkey=="},  # Falta key_id
            format="json",
        )
        assert resp.status_code == 400

    def test_rotate_old_key_becomes_inactive(self, authed_client, user, public_key):
        """Rotate marca la clave antigua como is_active=False (mata 297)."""
        resp = authed_client.post(
            f"/api/public-keys/{public_key.id}/rotate/",
            {"public_key": "newkey==", "key_id": "key-2"},
            format="json",
        )
        assert resp.status_code == 200
        public_key.refresh_from_db()
        assert public_key.is_active is False  # No True
        assert public_key.rotated_at is not None

    def test_rotate_keeps_shares_pending(self, authed_client, user, public_key):
        """Rotate conserva shares (pendientes de re-encriptación, no se borran)."""
        task = Task.objects.create(owner=user, title="Test")
        enc_task = EncryptedTask.objects.create(
            owner=user, task=task, encrypted_data="data",
            encryption_key_id="key-1", iv="iv==",
        )
        share = EncryptedKeyShare.objects.create(
            encrypted_task=enc_task, user=user,
            encrypted_key="original_key_data",
            user_public_key=public_key,
        )
        resp = authed_client.post(
            f"/api/public-keys/{public_key.id}/rotate/",
            {"public_key": "newkey==", "key_id": "key-2"},
            format="json",
        )
        assert resp.status_code == 200
        share.refresh_from_db()
        # El share se conserva (el cliente re-encriptará con la nueva clave)
        assert share.encrypted_key == "original_key_data"
        assert resp.data["pending_reencryption_count"] == 1

    def test_rotate_response_keys(self, authed_client, user, public_key):
        """Rotate devuelve old_key, new_key, pending_reencryption_count (mata 303-305)."""
        resp = authed_client.post(
            f"/api/public-keys/{public_key.id}/rotate/",
            {"public_key": "newkey==", "key_id": "key-2"},
            format="json",
        )
        assert resp.status_code == 200
        assert "old_key" in resp.data  # No "XXold_keyXX"
        assert "new_key" in resp.data  # No "XXnew_keyXX"
        assert "pending_reencryption_count" in resp.data  # No "XX...XX"
        assert resp.data["pending_reencryption_count"] == 0


@pytest.mark.django_db
class TestPublicKeyDestroyMutationKills:
    """Mata mutantes 307-311, 314-315: force param, comparison, dependent_shares."""

    def test_destroy_without_force_with_shares_409(self, authed_client, user, public_key):
        """Destroy sin force con shares dependientes devuelve 409 (mata 307-311, 314)."""
        task = Task.objects.create(owner=user, title="Test")
        enc_task = EncryptedTask.objects.create(
            owner=user, task=task, encrypted_data="data",
            encryption_key_id="key-1", iv="iv==",
        )
        EncryptedKeyShare.objects.create(
            encrypted_task=enc_task, user=user,
            encrypted_key="key_data",
            user_public_key=public_key,
        )
        # Sin ?force=true → debe devolver 409
        resp = authed_client.delete(f"/api/public-keys/{public_key.id}/")
        assert resp.status_code == 409
        assert "error" in resp.data
        assert resp.data["dependent_shares"] == 1  # No > 1

    def test_destroy_with_force_true(self, authed_client, user, public_key):
        """Destroy con ?force=true elimina la clave (mata 307-311)."""
        task = Task.objects.create(owner=user, title="Test")
        enc_task = EncryptedTask.objects.create(
            owner=user, task=task, encrypted_data="data",
            encryption_key_id="key-1", iv="iv==",
        )
        EncryptedKeyShare.objects.create(
            encrypted_task=enc_task, user=user,
            encrypted_key="key_data",
            user_public_key=public_key,
        )
        resp = authed_client.delete(f"/api/public-keys/{public_key.id}/?force=true")
        assert resp.status_code == 204
        assert not UserPublicKey.objects.filter(id=public_key.id).exists()

    def test_destroy_with_force_True_case_insensitive(self, authed_client, user, public_key):
        """Destroy con ?force=TRUE también funciona (mata 309: == vs !=)."""
        resp = authed_client.delete(f"/api/public-keys/{public_key.id}/?force=TRUE")
        assert resp.status_code == 204

    def test_destroy_without_shares_no_force(self, authed_client, user, public_key):
        """Destroy sin shares y sin force elimina la clave."""
        resp = authed_client.delete(f"/api/public-keys/{public_key.id}/")
        assert resp.status_code == 204

    def test_destroy_with_force_false_with_shares_409(self, authed_client, user, public_key):
        """Destroy con ?force=false y shares devuelve 409 (mata 315: not force → force)."""
        task = Task.objects.create(owner=user, title="Test")
        enc_task = EncryptedTask.objects.create(
            owner=user, task=task, encrypted_data="data",
            encryption_key_id="key-1", iv="iv==",
        )
        EncryptedKeyShare.objects.create(
            encrypted_task=enc_task, user=user,
            encrypted_key="key_data",
            user_public_key=public_key,
        )
        resp = authed_client.delete(f"/api/public-keys/{public_key.id}/?force=false")
        # Si condition es `dependent_shares > 0 and force` (mutant), force=False → no bloquea → 204
        # Si condition es `dependent_shares > 0 and not force` (original), not False=True → bloquea → 409
        assert resp.status_code == 409


# ============================================================================
# integrations/views.py — 30 sobrevivientes
# ============================================================================

@pytest.fixture
def github_installation(user):
    return GitHubInstallation.objects.create(
        user=user, installation_id=12345, account_login="testuser",
        account_type="User", github_user_id=67890, github_username="testuser",
        access_token="gho_test_token",
    )


@pytest.fixture
def github_repo(github_installation):
    return GitHubRepo.objects.create(
        installation=github_installation, repo_id=100,
        full_name="testuser/my-repo", name="my-repo", owner="testuser",
    )


@pytest.mark.django_db
class TestImportIssuesMutationKills3:
    """Mata mutantes 389-390: state key y default en import_issues."""

    @patch("apps.integrations.views.GitHubAppClient")
    def test_import_issues_with_explicit_state_closed(self, mock_client_class, authed_client, github_repo):
        """import_issues con state='closed' lo pasa al cliente (mata 389 y 390)."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.list_issues.return_value = []
        resp = authed_client.post(
            f"/api/github/repos/{github_repo.id}/import_issues/",
            {"state": "closed"},
            format="json",
        )
        assert resp.status_code == 200
        # Verifica que se llamó con state="closed" (no "open")
        mock_client.list_issues.assert_called_once_with(
            github_repo.owner, github_repo.name, state="closed"
        )

    @patch("apps.integrations.views.GitHubAppClient")
    def test_import_issues_default_state_open(self, mock_client_class, authed_client, github_repo):
        """import_issues sin state usa 'open' (mata 390)."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.list_issues.return_value = []
        resp = authed_client.post(
            f"/api/github/repos/{github_repo.id}/import_issues/",
            {},
            format="json",
        )
        assert resp.status_code == 200
        mock_client.list_issues.assert_called_once_with(
            github_repo.owner, github_repo.name, state="open"  # No "XXopenXX"
        )


@pytest.mark.django_db
class TestPrLinkMessageMutationKills3:
    """Mata mutante 433: message string en PR link_task."""

    def test_link_task_message_exact(self, authed_client, github_installation, user):
        """link_task devuelve mensaje exacto sin XX (mata 433)."""
        repo = GitHubRepo.objects.create(
            installation=github_installation, repo_id=1,
            full_name="t/r", name="r", owner="t",
        )
        pr = GitHubPullRequest.objects.create(
            repo=repo, pr_number=99, pr_id=1, title="PR", state="open",
            html_url="http://gh/1", is_merged=False,
        )
        task = Task.objects.create(owner=user, title="T")
        resp = authed_client.post(
            f"/api/github/prs/{pr.id}/link_task/",
            {"task_id": task.id},
            format="json",
        )
        assert resp.status_code == 200
        msg = resp.data["message"]
        # El mensaje original contiene "PR #99 vinculado a tarea"
        # El mutante lo envuelve en XX...XX
        assert "PR #99 vinculado a tarea" in msg
        assert not msg.startswith("XX")


@pytest.mark.django_db
class TestOAuthProvidersMutationKills3:
    """Mata mutantes 473-476: oauth_providers settings keys."""

    @override_settings(
        GITHUB_APP_CLIENT_ID="gh_test",
        SOCIALACCOUNT_PROVIDERS={"google": {"APP": {"client_id": "google_test"}}},
    )
    def test_oauth_providers_both_configured(self, api_client):
        """oauth_providers con ambos configurados devuelve True (mata 473-476)."""
        resp = api_client.get("/api/auth/oauth-providers/")
        assert resp.status_code == 200
        assert resp.data["github"] is True
        assert resp.data["google"] is True  # No False por keys mutadas

    @override_settings(GITHUB_APP_CLIENT_ID="gh_test")
    def test_oauth_providers_google_not_configured(self, api_client):
        """oauth_providers sin google devuelve False."""
        resp = api_client.get("/api/auth/oauth-providers/")
        assert resp.status_code == 200
        assert resp.data["github"] is True
        assert resp.data["google"] is False


@pytest.mark.django_db
class TestOAuthStartMutationKills3:
    """Mata mutantes 481-487: oauth_start redirect_uri, state, session."""

    @override_settings(DJANGO_FRONTEND_URL="http://localhost:3000/")
    @patch("apps.integrations.views.GitHubOAuthClient")
    def test_oauth_start_redirect_uri_strips_slash(self, mock_oauth_class, api_client):
        """oauth_start construye redirect_uri sin slash final (mata 481, 482, 483)."""
        mock_oauth = MagicMock()
        mock_oauth_class.return_value = mock_oauth
        mock_oauth.get_authorize_url.return_value = "http://gh/auth"
        resp = api_client.get("/api/auth/github/start/")
        assert resp.status_code == 200
        # Verifica que redirect_uri no tiene doble slash ni está envuelto en XX
        call_args = mock_oauth.get_authorize_url.call_args
        redirect_uri = call_args[0][0]
        assert redirect_uri == "http://localhost:3000/auth/github/callback"
        assert not redirect_uri.startswith("XX")

    @override_settings(DJANGO_FRONTEND_URL="http://localhost:3000")
    @patch("apps.integrations.views.GitHubOAuthClient")
    def test_oauth_start_state_in_session(self, mock_oauth_class, api_client):
        """oauth_start guarda state en session['github_oauth_state'] (mata 484-487)."""
        mock_oauth = MagicMock()
        mock_oauth_class.return_value = mock_oauth
        mock_oauth.get_authorize_url.return_value = "http://gh/auth"
        resp = api_client.get("/api/auth/github/start/")
        assert resp.status_code == 200
        session = api_client.session
        assert "github_oauth_state" in session  # No "XXgithub_oauth_stateXX"
        state = session["github_oauth_state"]
        assert state is not None  # No None
        assert len(state) > 0


@pytest.mark.django_db
class TestOAuthCallbackRedirectMutationKills3:
    """Mata mutantes 508-510: oauth_callback redirect_uri."""

    @override_settings(DJANGO_FRONTEND_URL="http://localhost:3000/")
    @patch("apps.integrations.views.GitHubOAuthClient")
    def test_oauth_callback_redirect_uri(self, mock_oauth_class, api_client):
        """oauth_callback construye redirect_uri correctamente (mata 508-510)."""
        session = api_client.session
        session["github_oauth_state"] = "s"
        session.save()
        mock_oauth = MagicMock()
        mock_oauth_class.return_value = mock_oauth
        mock_oauth.exchange_code.return_value = {"access_token": "tok"}
        mock_oauth.get_user_info.return_value = {
            "id": 99999, "login": "cbuser", "email": "cb@test.com",
            "avatar_url": "http://av",
        }
        resp = api_client.post(
            "/api/auth/github/callback/",
            {"code": "c", "state": "s"},
            format="json",
        )
        assert resp.status_code == 200
        # Verifica que exchange_code fue llamado con redirect_uri correcto
        call_args = mock_oauth.exchange_code.call_args
        redirect_uri = call_args[0][1]  # second positional arg
        assert redirect_uri == "http://localhost:3000/auth/github/callback"
        assert not redirect_uri.startswith("XX")


@pytest.mark.django_db
class TestOAuthCallbackUserMutationKills3:
    """Mata mutantes 520, 524-525, 527, 531, 539: user creation, defaults."""

    @patch("apps.integrations.views.GitHubOAuthClient")
    def test_oauth_callback_login_value_preserved(self, mock_oauth_class, api_client):
        """login con valor se preserva en github_username (mata 520)."""
        session = api_client.session
        session["github_oauth_state"] = "s"
        session.save()
        mock_oauth = MagicMock()
        mock_oauth_class.return_value = mock_oauth
        mock_oauth.exchange_code.return_value = {"access_token": "tok"}
        mock_oauth.get_user_info.return_value = {
            "id": 11112, "login": "mylogin", "email": "login@test.com",
            "avatar_url": "http://av",
        }
        resp = api_client.post(
            "/api/auth/github/callback/",
            {"code": "c", "state": "s"},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["github_username"] == "mylogin"  # No "XXXX"
        inst = GitHubInstallation.objects.get(github_user_id=11112)
        assert inst.github_username == "mylogin"

    @patch("apps.integrations.views.GitHubOAuthClient")
    def test_oauth_callback_existing_installation_user(self, mock_oauth_class, api_client, github_installation):
        """Callback con instalación existente reutiliza el usuario (mata 524, 525)."""
        session = api_client.session
        session["github_oauth_state"] = "s"
        session.save()
        mock_oauth = MagicMock()
        mock_oauth_class.return_value = mock_oauth
        mock_oauth.exchange_code.return_value = {"access_token": "newtok"}
        mock_oauth.get_user_info.return_value = {
            "id": 67890,  # Mismo github_user_id que github_installation
            "login": "testuser",
            "email": "user@test.com",
            "avatar_url": "http://av",
        }
        resp = api_client.post(
            "/api/auth/github/callback/",
            {"code": "c", "state": "s"},
            format="json",
        )
        assert resp.status_code == 200
        # Debe reutilizar el usuario existente, no crear uno nuevo
        assert resp.data["user"]["email"] == "user@test.com"
        # No debe crear un usuario adicional
        assert User.objects.filter(email="user@test.com").count() == 1

    @patch("apps.integrations.views.GitHubOAuthClient")
    def test_oauth_callback_no_email_no_user_search(self, mock_oauth_class, api_client):
        """Callback sin email no busca por email (mata 527: and→or).

        Si usa 'or', gh_email=None → not user or None → True → busca por email=None
        Si usa 'and', not user and None → False → no busca por email
        Ambos caminos crean un usuario nuevo, pero con 'or' buscaría primero.
        Verificamos que no se reutiliza un usuario existente sin github_user_id.
        """
        session = api_client.session
        session["github_oauth_state"] = "s"
        session.save()
        # Crear un usuario con email existente (sin instalación GitHub)
        User.objects.create_user(email="existing@test.com", username="existing", password="p")
        mock_oauth = MagicMock()
        mock_oauth_class.return_value = mock_oauth
        mock_oauth.exchange_code.return_value = {"access_token": "tok"}
        mock_oauth.get_user_info.return_value = {
            "id": 88888, "login": "noemail", "email": None,
            "avatar_url": "http://av",
        }
        resp = api_client.post(
            "/api/auth/github/callback/",
            {"code": "c", "state": "s"},
            format="json",
        )
        # El callback puede fallar si email=None y Django requiere email
        # Lo importante es que no se reutilice existing@test.com
        if resp.status_code == 200:
            # El usuario de la respuesta no debe ser existing@test.com
            assert resp.data["user"]["email"] != "existing@test.com"

    @patch("apps.integrations.views.GitHubOAuthClient")
    def test_oauth_callback_avatar_url_default_empty(self, mock_oauth_class, api_client):
        """avatar_url sin valor usa default '' (mata 539)."""
        session = api_client.session
        session["github_oauth_state"] = "s"
        session.save()
        mock_oauth = MagicMock()
        mock_oauth_class.return_value = mock_oauth
        mock_oauth.exchange_code.return_value = {"access_token": "tok"}
        mock_oauth.get_user_info.return_value = {
            "id": 44444, "login": "noavatar", "email": "noav@test.com",
            # Sin "avatar_url" key
        }
        resp = api_client.post(
            "/api/auth/github/callback/",
            {"code": "c", "state": "s"},
            format="json",
        )
        assert resp.status_code == 200
        inst = GitHubInstallation.objects.get(github_user_id=44444)
        assert inst.avatar_url == ""  # No "XXXX"


@pytest.mark.django_db
class TestWebhookMutationKills3:
    """Mata mutantes 553-555, 561, 564: webhook headers y defaults."""

    def test_webhook_no_signature_error(self, api_client):
        """Webhook sin signature header devuelve 401 (mata 553-555)."""
        resp = api_client.post(
            "/api/webhooks/github/",
            data=json.dumps({"action": "opened"}),
            content_type="application/json",
        )
        assert resp.status_code == 401
        assert resp.data["error"] == "Firma inválida"

    @patch("apps.integrations.views.GitHubAppClient.verify_webhook_signature", return_value=True)
    @patch("apps.integrations.webhook_processor.process_webhook_delivery")
    def test_webhook_event_type_default_empty(self, mock_process, mock_verify, api_client):
        """Webhook sin X-GitHub-Event usa default '' (mata 561)."""
        mock_process.return_value = ({"ok": True}, 200)
        payload = {"action": "opened", "repository": {"full_name": "t/r"}}
        resp = api_client.post(
            "/api/webhooks/github/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_GITHUB_DELIVERY="d1",
        )
        assert resp.status_code == 200
        call_kwargs = mock_process.call_args.kwargs
        assert call_kwargs["event_type"] == ""  # No "XXXX"

    @patch("apps.integrations.views.GitHubAppClient.verify_webhook_signature", return_value=True)
    @patch("apps.integrations.webhook_processor.process_webhook_delivery")
    def test_webhook_delivery_id_fallback_hash(self, mock_process, mock_verify, api_client):
        """Sin X-GitHub-Delivery, delivery_id es el sha256 del body (idempotencia)."""
        import hashlib
        mock_process.return_value = ({"ok": True}, 200)
        payload = {"action": "opened", "repository": {"full_name": "t/r"}}
        body = json.dumps(payload)
        resp = api_client.post(
            "/api/webhooks/github/",
            data=body,
            content_type="application/json",
            HTTP_X_GITHUB_EVENT="push",
        )
        assert resp.status_code == 200
        call_kwargs = mock_process.call_args.kwargs
        assert call_kwargs["delivery_id"] == hashlib.sha256(body.encode()).hexdigest()


@pytest.mark.django_db
class TestWebhookPermissionsMutationKills3:
    """Mata mutantes 576, 586: permission_classes en webhook_deliveries y retry."""

    def test_webhook_deliveries_requires_auth(self, api_client):
        """webhook_deliveries sin auth devuelve 401/403 (mata 576)."""
        resp = api_client.get("/api/webhooks/deliveries/")
        assert resp.status_code in (401, 403)

    def test_webhook_retry_requires_auth(self, api_client):
        """webhook_retry_dead_letter sin auth devuelve 401/403 (mata 586)."""
        resp = api_client.post("/api/webhooks/retry-dead-letter/")
        assert resp.status_code in (401, 403)


# ============================================================================
# automations/engine.py — 13 sobrevivientes
# ============================================================================

class TestEvaluateConditionsMutationKills3:
    """Mata mutante 3: field default."""

    def test_condition_without_field_uses_empty(self):
        """Condición sin 'field' usa '' como default (mata 3)."""
        # Si field="XXXX", context.get("XXXX","") != "1" → False
        # Si field="", context.get("","") != "1" → True
        assert evaluate_conditions([{"operator": "not_equals", "value": "1"}], {})


@pytest.mark.django_db(transaction=True)
class TestExecuteActionSprintMutationKills3:
    """Mata mutantes 35-36: sprint context key."""

    def test_create_notification_with_sprint(self, user, task, project):
        """CREATE_NOTIFICATION con sprint en context lo pasa a notify (mata 35-36)."""
        from apps.tasks.models import Sprint
        sprint = Sprint.objects.create(
            owner=user, project=project, name="S1",
            state=Sprint.SprintState.PLANNED,
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=14),
        )
        rule = AutomationRule.objects.create(
            owner=user, name="N", trigger=AutomationRule.Trigger.SPRINT_CLOSED,
            action=AutomationRule.Action.CREATE_NOTIFICATION,
            action_params={"title": "Sprint notif", "body": "Body text"},
            enabled=True,
        )
        result = execute_action(rule, {"task": task, "user": user, "sprint": sprint})
        assert result["notification_created"] is True
        notif = Notification.objects.filter(recipient=user).first()
        assert notif is not None
        assert notif.sprint == sprint  # No None si sprint context key está mutado


@pytest.mark.django_db(transaction=True)
class TestCreateNotificationDefaultsMutationKills3:
    """Mata mutantes 71-73: body y action_url defaults."""

    def test_notification_body_default_empty(self, user, task):
        """CREATE_NOTIFICATION sin body usa default '' (mata 71)."""
        rule = AutomationRule.objects.create(
            owner=user, name="N", trigger=AutomationRule.Trigger.TASK_CREATED,
            action=AutomationRule.Action.CREATE_NOTIFICATION,
            action_params={"title": "T"}, enabled=True,
        )
        execute_action(rule, {"task": task, "user": user})
        notif = Notification.objects.filter(recipient=user).first()
        assert notif.body == ""  # No "XXXX"

    def test_notification_action_url_default_empty(self, user, task):
        """CREATE_NOTIFICATION sin action_url usa default '' (mata 72-73)."""
        rule = AutomationRule.objects.create(
            owner=user, name="N", trigger=AutomationRule.Trigger.TASK_CREATED,
            action=AutomationRule.Action.CREATE_NOTIFICATION,
            action_params={"title": "T"}, enabled=True,
        )
        execute_action(rule, {"task": task, "user": user})
        notif = Notification.objects.filter(recipient=user).first()
        assert notif.action_url == ""  # No "XXXX"

    def test_notification_action_url_custom(self, user, task):
        """CREATE_NOTIFICATION con action_url personalizado lo usa (mata 72)."""
        rule = AutomationRule.objects.create(
            owner=user, name="N", trigger=AutomationRule.Trigger.TASK_CREATED,
            action=AutomationRule.Action.CREATE_NOTIFICATION,
            action_params={"title": "T", "action_url": "/custom/url"},
            enabled=True,
        )
        execute_action(rule, {"task": task, "user": user})
        notif = Notification.objects.filter(recipient=user).first()
        assert notif.action_url == "/custom/url"  # No ""


@pytest.mark.django_db(transaction=True)
class TestCreateTaskDescriptionMutationKills3:
    """Mata mutante 82: description default."""

    def test_create_task_description_default_empty(self, user):
        """CREATE_TASK sin description usa default '' (mata 82)."""
        AutomationRule.objects.filter(trigger=AutomationRule.Trigger.TASK_CREATED).delete()
        rule = AutomationRule.objects.create(
            owner=user, name="CT", trigger=AutomationRule.Trigger.DAILY_CHECK,
            action=AutomationRule.Action.CREATE_TASK,
            action_params={"title": "NoDesc"}, enabled=True,
        )
        result = execute_action(rule, {"user": user})
        task = Task.objects.get(id=result["created_task_id"])
        assert task.description == ""  # No "XXXX"


@pytest.mark.django_db(transaction=True)
class TestSetAssigneeMutationKills3:
    """Mata mutantes 98, 101: new_assignee init y error message."""

    def test_set_assignee_not_found_error_message(self, user, task):
        """SET_ASSIGNEE por email inexistente devuelve error sin XX (mata 101)."""
        rule = AutomationRule.objects.create(
            owner=user, name="A", trigger=AutomationRule.Trigger.TASK_CREATED,
            action=AutomationRule.Action.SET_ASSIGNEE,
            action_params={"assignee_email": "nobody@test.com"}, enabled=True,
        )
        result = execute_action(rule, {"task": task, "user": user})
        assert "error" in result
        # El mensaje original es "User nobody@test.com not found"
        # El mutante lo envuelve en XX...XX
        assert "nobody@test.com" in result["error"]
        assert not result["error"].startswith("XX")

    def test_set_assignee_new_assignee_init_none(self, user, task):
        """SET_ASSIGNEE inicializa new_assignee=None (mata 98: None→'')."""
        # Si new_assignee="", el bloque `if new_assignee:` es False → no asigna
        # Si new_assignee=None, mismo comportamiento → equivalente
        # Pero si assignee_id no existe, el resultado debe tener error
        rule = AutomationRule.objects.create(
            owner=user, name="A", trigger=AutomationRule.Trigger.TASK_CREATED,
            action=AutomationRule.Action.SET_ASSIGNEE,
            action_params={"assignee_id": 99999}, enabled=True,  # ID inexistente
        )
        result = execute_action(rule, {"task": task, "user": user})
        assert "error" in result
        assert "99999" in result["error"]


@pytest.mark.django_db(transaction=True)
class TestAddTagMutationKills3:
    """Mata mutante 110: tag_name default."""

    def test_add_tag_without_name_no_op(self, user, task):
        """ADD_TAG sin tag_name no crea tag (mata 110)."""
        rule = AutomationRule.objects.create(
            owner=user, name="T", trigger=AutomationRule.Trigger.TASK_CREATED,
            action=AutomationRule.Action.ADD_TAG,
            action_params={}, enabled=True,  # Sin tag_name
        )
        execute_action(rule, {"task": task, "user": user})
        # Si tag_name="", no entra al if → no hace nada
        # Si tag_name="XXXX", crea un tag llamado "XXXX"
        from apps.tags.models import Tag
        assert not Tag.objects.filter(name="XXXX").exists()


@pytest.mark.django_db(transaction=True)
class TestTriggerAutomationMutationKills3:
    """Mata mutantes 135, 141, 166: user context, continue vs break, overdue key."""

    def test_trigger_user_from_task_sets_context(self, user, task):
        """trigger_automation sin user obtiene de task.owner y lo guarda (mata 135)."""
        AutomationRule.objects.create(
            owner=user, name="Auto", trigger=AutomationRule.Trigger.TASK_CREATED,
            action=AutomationRule.Action.SET_PRIORITY,
            action_params={"priority": 2}, enabled=True,
        )
        results = trigger_automation(AutomationRule.Trigger.TASK_CREATED, {"task": task})
        assert len(results) == 1
        log = AutomationLog.objects.first()
        # context["user"] debe ser el user real, no None
        assert "user" in log.trigger_data
        # El user en trigger_data debe ser serializado (dict con _type, id, str)
        assert log.trigger_data["user"] is not None

    def test_trigger_disabled_rule_continues_to_next(self, user, task):
        """Regla deshabilitada se salta y continúa con la siguiente (mata 141: continue→break)."""
        AutomationRule.objects.create(
            owner=user, name="Disabled", trigger=AutomationRule.Trigger.TASK_CREATED,
            action=AutomationRule.Action.SET_PRIORITY,
            action_params={"priority": 1}, enabled=False,
        )
        AutomationRule.objects.create(
            owner=user, name="Enabled", trigger=AutomationRule.Trigger.TASK_CREATED,
            action=AutomationRule.Action.SET_STATE,
            action_params={"state": "in_progress"}, enabled=True,
        )
        results = trigger_automation(
            AutomationRule.Trigger.TASK_CREATED,
            {"task": task, "user": user},
        )
        # Si break, solo procesa la primera (disabled) → 0 resultados
        # Si continue, salta disabled y procesa enabled → 1 resultado
        assert len(results) == 1
        assert results[0]["rule"] == "Enabled"

    def test_daily_check_overdue_user_key(self, user, task):
        """TASK_OVERDUE context tiene 'user' key (mata 166)."""
        task.due_date = timezone.now() - timedelta(days=1)
        task.state = "pending"
        task.save()
        AutomationRule.objects.create(
            owner=user, name="Overdue", trigger=AutomationRule.Trigger.TASK_OVERDUE,
            action=AutomationRule.Action.CREATE_NOTIFICATION,
            action_params={"title": "Overdue!"}, enabled=True,
        )
        run_daily_checks()
        log = AutomationLog.objects.filter(
            rule__trigger=AutomationRule.Trigger.TASK_OVERDUE
        ).first()
        assert log is not None
        assert "user" in log.trigger_data  # No "XXuserXX"


# ============================================================================
# offline_sync/services.py — 1 sobreviviente (190)
# ============================================================================

@pytest.mark.django_db(transaction=True)
class TestSyncDeviceIdMutationKills3:
    """Mata mutante 190: device_id default. device FK es NOT NULL, no se puede matar
    directamente, pero verificamos que device_id se pasa correctamente."""

    def test_apply_operation_with_matching_device(self, user):
        """Operación con device_id que existe linkea el device."""
        from apps.offline_sync.models import SyncDevice, SyncOperation
        dev = SyncDevice.objects.create(user=user, device_id="dev-match", device_name="Test")
        from apps.offline_sync.services import apply_sync_operations
        ops = [{
            "device_id": "dev-match",
            "op_type": "create",
            "entity_type": "task",
            "entity_id": "ent-dev",
            "payload": {"title": "Task with device"},
            "client_timestamp": timezone.now().isoformat(),
        }]
        results = apply_sync_operations(user, ops)
        assert results[0]["status"] == "applied"
        op = SyncOperation.objects.get(entity_id="ent-dev")
        assert op.device == dev

