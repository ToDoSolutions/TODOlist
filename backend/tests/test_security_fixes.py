"""Tests de regresión para los fixes de seguridad (auditoría).

Cubre: recursión de automatizaciones, mass assignment en bulk ops,
IDOR en miembros de proyecto, SavedSearch compartidas, 2FA en login,
backup codes hasheados, scopes de API key, firma de webhooks,
offline sync (hijacking/base_version), cifrado E2E y SSRF en chat.
"""
import hashlib
import hmac
import json

import pytest
from django.test import override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.automations.models import AutomationLog, AutomationRule
from apps.collaboration.models import ProjectMember
from apps.encryption.models import EncryptedKeyShare, EncryptedTask, UserPublicKey
from apps.offline_sync.models import SyncDevice
from apps.tasks.models import SavedSearch, Sprint, Task
from apps.users.models import APIKey, TwoFactorSecret, User
from apps.users.security import hash_backup_code


@pytest.fixture
def client_b(other_user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(other_user).access_token}")
    return c


# --- Automatizaciones ---

@pytest.mark.django_db
class TestAutomationRecursion:
    def test_create_task_rule_no_infinite_loop(self, user):
        """Una regla TASK_CREATED→CREATE_TASK no debe hacer bucle infinito."""
        AutomationRule.objects.create(
            owner=user, name="loop", trigger="task_created",
            action="create_task", action_params={"title": "child"}, enabled=True,
        )
        # Si hay recursión infinita esto lanzaría RecursionError
        Task.objects.create(owner=user, title="origen")
        # La regla se disparó a lo sumo _MAX_AUTOMATION_DEPTH veces
        total = Task.objects.filter(owner=user, title="child").count()
        assert 1 <= total <= 5

    def test_state_change_chain_bounded(self, user):
        """Reglas encadenadas (pending→in_progress→completed) se ejecutan con límite."""
        AutomationRule.objects.create(
            owner=user, name="a", trigger="task_state_changed",
            conditions=[{"field": "new_state", "operator": "equals", "value": "in_progress"}],
            action="set_state", action_params={"state": "completed"}, enabled=True,
        )
        task = Task.objects.create(owner=user, title="t", state="pending")
        task.state = "in_progress"
        task.save()
        task.refresh_from_db()
        assert task.state == "completed"

    def test_set_state_invalid_rejected(self, user):
        """SET_STATE con estado inválido no debe aplicarse."""
        rule = AutomationRule.objects.create(
            owner=user, name="bad", trigger="task_created",
            action="set_state", action_params={"state": "hacked"}, enabled=True,
        )
        task = Task.objects.create(owner=user, title="t")
        task.refresh_from_db()
        assert task.state != "hacked"
        assert AutomationLog.objects.filter(rule=rule).exists()

    def test_rule_test_endpoint_is_dry_run(self, authed_client, user, task):
        """POST /test no ejecuta acciones reales."""
        rule = AutomationRule.objects.create(
            owner=user, name="r", trigger="task_created",
            action="set_state", action_params={"state": "completed"}, enabled=True,
        )
        resp = authed_client.post(f"/api/automation-rules/{rule.id}/test/")
        assert resp.status_code == 200
        task.refresh_from_db()
        assert task.state == "pending"  # no se aplicó
        assert resp.data["would_execute"] is True


# --- Bulk operations ---

@pytest.mark.django_db
class TestBulkOperations:
    def test_bulk_update_rejects_protected_fields(self, authed_client, user, task):
        """Mass assignment: owner/version/completed_at no son modificables."""
        other = User.objects.create_user(email="x@x.com", username="x", password="p")
        resp = authed_client.post("/api/tasks/bulk_update/", {
            "task_ids": [task.id],
            "updates": {"owner": other.id},
        }, format="json")
        assert resp.status_code == 400
        task.refresh_from_db()
        assert task.owner_id == user.id

    def test_bulk_update_allowed_field(self, authed_client, user, task):
        resp = authed_client.post("/api/tasks/bulk_update/", {
            "task_ids": [task.id],
            "updates": {"priority": 5},
        }, format="json")
        assert resp.status_code == 200
        task.refresh_from_db()
        assert task.priority == 5

    def test_bulk_update_size_cap(self, authed_client, user):
        resp = authed_client.post("/api/tasks/bulk_update/", {
            "task_ids": list(range(1000)),
            "updates": {"priority": 3},
        }, format="json")
        assert resp.status_code == 400

    def test_bulk_move_sprint_rejects_foreign(self, authed_client, user, task, other_user):
        from django.utils import timezone

        from apps.projects.models import Project
        foreign_project = Project.objects.create(owner=other_user, name="Ajeno")
        foreign = Sprint.objects.create(
            owner=other_user, name="Ajeno", project=foreign_project,
            start_date=timezone.localdate(), end_date=timezone.localdate(),
        )
        resp = authed_client.post("/api/tasks/bulk_move_sprint/", {
            "task_ids": [task.id], "sprint_id": foreign.id,
        }, format="json")
        assert resp.status_code == 404
        task.refresh_from_db()
        assert task.sprint_id != foreign.id


# --- IDOR colaboración ---

@pytest.mark.django_db
class TestCollaborationAuthz:
    def test_create_member_in_foreign_project_forbidden(self, client_b, other_user, project):
        """Usuario B no puede añadir miembros al proyecto de A."""
        third = User.objects.create_user(email="t@t.com", username="t", password="p")
        resp = client_b.post("/api/project-members/", {
            "project": project.id, "user": third.id, "role": "editor",
        }, format="json")
        assert resp.status_code in (400, 403)
        assert not ProjectMember.objects.filter(project=project, user=third).exists()

    def test_invite_foreign_project_forbidden(self, client_b, other_user, project):
        resp = client_b.post("/api/project-members/invite/", {
            "email": other_user.email, "project_id": project.id,
        }, format="json")
        assert resp.status_code == 403

    def test_member_cannot_escalate_own_role(self, client_b, user, project, other_user):
        """Un miembro no puede cambiar su propio rol a owner."""
        member = ProjectMember.objects.create(project=project, user=other_user, role="viewer")
        resp = client_b.patch(f"/api/project-members/{member.id}/", {"role": "owner"}, format="json")
        assert resp.status_code == 403
        member.refresh_from_db()
        assert member.role == "viewer"

    def test_invitation_to_foreign_target(self, client_b, project):
        """No se puede invitar a un proyecto que no administras."""
        resp = client_b.post("/api/invitations/", {
            "target_type": "project", "target_id": project.id,
            "email": "x@x.com", "role": "editor",
        }, format="json")
        assert resp.status_code in (400, 403)


# --- SavedSearch ---

@pytest.mark.django_db
class TestSavedSearchSharing:
    def test_cannot_modify_shared_foreign_search(self, client_b, user, other_user):
        ss = SavedSearch.objects.create(owner=user, name="S", is_shared=True)
        resp = client_b.patch(f"/api/saved-searches/{ss.id}/", {"name": "Hackeada"}, format="json")
        assert resp.status_code == 403
        ss.refresh_from_db()
        assert ss.name == "S"

    def test_can_read_shared_search(self, client_b, user):
        ss = SavedSearch.objects.create(owner=user, name="S", is_shared=True)
        resp = client_b.get(f"/api/saved-searches/{ss.id}/")
        assert resp.status_code == 200


# --- 2FA en login ---

@pytest.mark.django_db
class TestTwoFactorLogin:
    def _enable_2fa(self, user):
        import pyotp
        secret = pyotp.random_base32()
        TwoFactorSecret.objects.create(user=user, secret=secret, is_enabled=True)
        return secret

    def test_login_without_2fa_works(self, client, user):
        resp = client.post("/api/auth/login/", {
            "email": user.email, "password": "testpass123",
        }, content_type="application/json")
        assert resp.status_code == 200
        assert "access" in resp.json()

    def test_login_with_2fa_requires_code(self, client, user):
        self._enable_2fa(user)
        resp = client.post("/api/auth/login/", {
            "email": user.email, "password": "testpass123",
        }, content_type="application/json")
        assert resp.status_code == 400
        assert "totp_code" in resp.json()

    def test_login_with_valid_totp(self, client, user):
        import pyotp
        secret = self._enable_2fa(user)
        code = pyotp.TOTP(secret).now()
        resp = client.post("/api/auth/login/", {
            "email": user.email, "password": "testpass123", "totp_code": code,
        }, content_type="application/json")
        assert resp.status_code == 200
        assert "access" in resp.json()

    def test_login_with_wrong_totp(self, client, user):
        self._enable_2fa(user)
        resp = client.post("/api/auth/login/", {
            "email": user.email, "password": "testpass123", "totp_code": "000000",
        }, content_type="application/json")
        assert resp.status_code == 400

    def test_backup_codes_stored_hashed(self, user):
        """Los backup codes se guardan hasheados, nunca en claro."""
        tf = TwoFactorSecret.objects.create(user=user, secret="ABC", is_enabled=True)
        codes = tf.generate_backup_codes()
        tf.refresh_from_db()
        for code in codes:
            assert code not in tf.backup_codes
            assert hash_backup_code(code) in tf.backup_codes
        # Y siguen siendo utilizables una vez
        assert tf.use_backup_code(codes[0]) is True
        assert tf.use_backup_code(codes[0]) is False  # consumido


# --- API key scopes ---

@pytest.mark.django_db
class TestAPIKeyScopes:
    def _client_with_key(self, user, scopes):
        raw, hashed, prefix = APIKey.generate_key()
        APIKey.objects.create(
            user=user, name="k", key_prefix=prefix, hashed_key=hashed, scopes=scopes,
        )
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"ApiKey {raw}")
        return c

    def test_readonly_key_can_read(self, user, task):
        c = self._client_with_key(user, ["read"])
        resp = c.get("/api/tasks/")
        assert resp.status_code == 200

    def test_readonly_key_cannot_write(self, user):
        c = self._client_with_key(user, ["read"])
        resp = c.post("/api/tasks/", {"title": "x"}, format="json")
        assert resp.status_code == 403

    def test_write_key_can_write(self, user):
        c = self._client_with_key(user, ["write"])
        resp = c.post("/api/tasks/", {"title": "x"}, format="json")
        assert resp.status_code in (200, 201, 400)  # no 403 por scope

    def test_no_scope_key_denied(self, user):
        c = self._client_with_key(user, [])
        resp = c.get("/api/tasks/")
        assert resp.status_code == 403

    def test_invalid_scope_rejected_on_create(self, authed_client):
        resp = authed_client.post("/api/api-keys/", {
            "name": "k", "scopes": ["root", "superuser"],
        }, format="json")
        assert resp.status_code == 400


# --- Webhooks ---

@pytest.mark.django_db
class TestWebhookSecurity:
    def _signed_post(self, client, payload, secret, delivery="d1", event="issues"):
        body = json.dumps(payload).encode()
        sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return client.post(
            "/api/webhooks/github/", body, content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=sig,
            HTTP_X_GITHUB_EVENT=event,
            HTTP_X_GITHUB_DELIVERY=delivery,
        )

    @override_settings(GITHUB_APP_WEBHOOK_SECRET="")
    def test_empty_secret_rejects_all(self, client):
        """Con secret vacío NO se acepta ninguna firma."""
        body = b'{"action":"opened"}'
        sig = "sha256=" + hmac.new(b"", body, hashlib.sha256).hexdigest()
        resp = client.post(
            "/api/webhooks/github/", body, content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=sig, HTTP_X_GITHUB_EVENT="issues",
        )
        assert resp.status_code == 401

    @override_settings(GITHUB_APP_WEBHOOK_SECRET="s3cret")
    def test_invalid_json_returns_400(self, client):
        body = b"not json{"
        sig = "sha256=" + hmac.new(b"s3cret", body, hashlib.sha256).hexdigest()
        resp = client.post(
            "/api/webhooks/github/", body, content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=sig, HTTP_X_GITHUB_EVENT="issues",
        )
        assert resp.status_code == 400

    @override_settings(GITHUB_APP_WEBHOOK_SECRET="s3cret")
    def test_missing_delivery_id_still_idempotent(self, client):
        """Sin X-GitHub-Delivery se deriva un id del body (no colapsa a '')."""
        payload = {"action": "unknown", "repository": {"full_name": "a/b"}}
        r1 = self._signed_post(client, payload, "s3cret", delivery="")
        r2 = self._signed_post(client, payload, "s3cret", delivery="")
        assert r1.status_code == 200
        assert r2.status_code == 200  # segunda entrega = idempotente


# --- Offline sync ---

@pytest.mark.django_db
class TestOfflineSyncSecurity:
    def test_device_hijacking_blocked(self, user, other_user):
        """Un device_id de otro usuario no puede reasignarse."""
        from django.core.exceptions import PermissionDenied

        from apps.offline_sync.services import register_device
        register_device(user, "dev-1", "mío")
        with pytest.raises(PermissionDenied):
            register_device(other_user, "dev-1", "robado")

    def test_revoked_device_cannot_push(self, authed_client, user, task):
        SyncDevice.objects.create(user=user, device_id="d1", is_active=False)
        resp = authed_client.post("/api/sync/push/", {
            "operations": [{
                "op_type": "update", "entity_type": "task",
                "entity_id": "e1", "device_id": "d1",
                "payload": {"id": task.id, "title": "x"}, "base_version": 1,
            }],
        }, format="json")
        assert resp.status_code == 403

    def test_update_without_base_version_rejected(self, authed_client, user, task):
        SyncDevice.objects.create(user=user, device_id="d1")
        resp = authed_client.post("/api/sync/push/", {
            "operations": [{
                "op_type": "update", "entity_type": "task",
                "entity_id": "e1", "device_id": "d1",
                "payload": {"id": task.id, "title": "x"},
            }],
        }, format="json")
        assert resp.status_code == 200
        assert resp.data["results"][0]["status"] == "rejected"

    def test_invalid_since_returns_400(self, authed_client):
        resp = authed_client.get("/api/sync/pull/?since=no-es-fecha")
        assert resp.status_code == 400


# --- Encryption ---

@pytest.mark.django_db
class TestEncryptionSecurity:
    def test_encrypted_task_foreign_rejected(self, authed_client, user, other_user):
        foreign_task = Task.objects.create(owner=other_user, title="ajena")
        resp = authed_client.post("/api/encrypted-tasks/", {
            "task": foreign_task.id,
            "encrypted_data": "abc", "encryption_key_id": "k1",
            "iv": "iv", "auth_tag": "tag", "algorithm": "AES-GCM",
        }, format="json")
        assert resp.status_code == 400
        assert not EncryptedTask.objects.filter(task=foreign_task).exists()

    def test_encrypted_task_requires_auth_tag(self, authed_client, user, task):
        resp = authed_client.post("/api/encrypted-tasks/", {
            "task": task.id, "encrypted_data": "abc",
            "encryption_key_id": "k1", "iv": "iv", "algorithm": "AES-GCM",
        }, format="json")
        assert resp.status_code == 400

    def test_rotate_preserves_key_shares(self, authed_client, user, other_user, task):
        """La rotación NO destruye los key shares existentes."""
        old_key = UserPublicKey.objects.create(
            user=user, public_key="pk1", key_id="k1", is_active=True,
        )
        et = EncryptedTask.objects.create(
            owner=user, task=task, encrypted_data="d",
            encryption_key_id="k1", iv="i", auth_tag="t", algorithm="AES-GCM",
        )
        share = EncryptedKeyShare.objects.create(
            encrypted_task=et, user=other_user,
            encrypted_key="EK", user_public_key=old_key,
        )
        resp = authed_client.post(f"/api/public-keys/{old_key.id}/rotate/", {
            "public_key": "pk2", "key_id": "k2",
        }, format="json")
        assert resp.status_code == 200
        share.refresh_from_db()
        assert share.encrypted_key == "EK"  # preservado, no vaciado

    def test_encrypted_task_excluida_de_search(self, authed_client, user):
        """Una Task vinculada a EncryptedTask no aparece en búsqueda FTS.

        Si el cliente ligó la Task con plaintext, la búsqueda la expondría
        en texto claro — se excluye defensivamente.
        """
        t = Task.objects.create(owner=user, title="contenido secreto xyz")
        EncryptedTask.objects.create(
            owner=user, task=t, encrypted_data="cipher",
            encryption_key_id="k", iv="i", auth_tag="t", algorithm="AES-GCM",
        )
        resp = authed_client.get("/api/tasks/search/?q=secreto")
        assert resp.status_code == 200
        titles = [r["title"] for r in resp.json()["results"]]
        assert "contenido secreto xyz" not in titles

    def test_ai_rechaza_tarea_cifrada(self, authed_client, user):
        """La IA no opera sobre tareas con contenido cifrado E2E."""
        t = Task.objects.create(owner=user, title="secreta")
        EncryptedTask.objects.create(
            owner=user, task=t, encrypted_data="cipher",
            encryption_key_id="k", iv="i", auth_tag="t", algorithm="AES-GCM",
        )
        resp = authed_client.post("/api/ai/estimate-priority/", {
            "task_id": t.id,
        }, format="json")
        assert resp.status_code == 404


# --- Chat integrations (SSRF) ---

@pytest.mark.django_db
class TestChatSSRF:
    def test_localhost_webhook_rejected(self, authed_client):
        resp = authed_client.post("/api/chat-integrations/", {
            "provider": "slack", "webhook_url": "http://localhost/hook",
        }, format="json")
        assert resp.status_code == 400

    def test_private_ip_webhook_rejected(self, authed_client):
        resp = authed_client.post("/api/chat-integrations/", {
            "provider": "slack", "webhook_url": "https://192.168.1.1/hook",
        }, format="json")
        assert resp.status_code == 400

    def test_webhook_url_not_exposed_in_read(self, authed_client, user):
        from unittest.mock import patch

        from apps.integrations_chat.models import ChatIntegration
        with patch("apps.integrations_chat.services._is_safe_url", return_value=True):
            ChatIntegration.objects.create(
                owner=user, provider="slack",
                webhook_url="https://hooks.slack.com/services/SECRET",
            )
        resp = authed_client.get("/api/chat-integrations/")
        data = resp.data.get("results", resp.data) if isinstance(resp.data, dict) else resp.data
        assert data
        assert "SECRET" not in json.dumps(data)
        assert "webhook_url" not in data[0]



# --- Acceso compartido por proyectos (ProjectMember roles) ---

@pytest.mark.django_db
class TestSharedProjectAccess:
    def test_member_can_read_project(self, client_b, user, other_user, project):
        ProjectMember.objects.create(project=project, user=other_user, role="viewer")
        resp = client_b.get(f"/api/projects/{project.id}/")
        assert resp.status_code == 200

    def test_non_member_cannot_read_project(self, client_b, project):
        resp = client_b.get(f"/api/projects/{project.id}/")
        assert resp.status_code == 404

    def test_member_cannot_update_project(self, client_b, other_user, project):
        """Solo el owner edita el proyecto (aunque sea miembro)."""
        ProjectMember.objects.create(project=project, user=other_user, role="editor")
        resp = client_b.patch(f"/api/projects/{project.id}/", {"name": "X"}, format="json")
        assert resp.status_code == 404  # queryset de escritura = solo owner

    def test_viewer_can_read_task_not_write(self, client_b, user, other_user, project, task):
        ProjectMember.objects.create(project=project, user=other_user, role="viewer")
        assert client_b.get(f"/api/tasks/{task.id}/").status_code == 200
        resp = client_b.patch(f"/api/tasks/{task.id}/", {"title": "x"}, format="json")
        assert resp.status_code == 403

    def test_editor_can_write_task(self, client_b, user, other_user, project, task):
        ProjectMember.objects.create(project=project, user=other_user, role="editor")
        resp = client_b.patch(f"/api/tasks/{task.id}/", {"title": "x"}, format="json")
        assert resp.status_code == 200

    def test_member_sees_shared_tasks_in_list(self, client_b, user, other_user, project, task):
        ProjectMember.objects.create(project=project, user=other_user, role="viewer")
        resp = client_b.get("/api/tasks/")
        data = resp.data if isinstance(resp.data, list) else resp.data.get("results", [])
        ids = [t["id"] for t in data]
        assert task.id in ids


# --- Aceptar invitación crea membresía ---

@pytest.mark.django_db
class TestInvitationAccept:
    def test_accept_creates_project_membership(self, client_b, user, other_user, project):
        from apps.collaboration.models import Invitation
        inv = Invitation.objects.create(
            target_type="project", target_id=project.id,
            email=other_user.email, role="editor",
            invited_by=user, token="tok-abc",
        )
        resp = client_b.post(f"/api/invitations/{inv.id}/accept/")
        assert resp.status_code == 200
        assert ProjectMember.objects.filter(project=project, user=other_user, role="editor").exists()

    def test_sender_cannot_accept(self, authed_client, user, other_user, project):
        """El emisor no puede aceptar la invitación en nombre del destinatario."""
        from apps.collaboration.models import Invitation
        inv = Invitation.objects.create(
            target_type="project", target_id=project.id,
            email=other_user.email, role="editor",
            invited_by=user, token="tok-def",
        )
        resp = authed_client.post(f"/api/invitations/{inv.id}/accept/")
        assert resp.status_code == 403
        assert not ProjectMember.objects.filter(project=project, user=user).exists()

    def test_invitation_role_cannot_be_owner(self, client_b, user, other_user, project):
        """Una invitación con role=owner no debe escalar a owner del proyecto."""
        from apps.collaboration.models import Invitation
        inv = Invitation.objects.create(
            target_type="project", target_id=project.id,
            email=other_user.email, role="owner",
            invited_by=user, token="tok-ghi",
        )
        resp = client_b.post(f"/api/invitations/{inv.id}/accept/")
        assert resp.status_code == 200
        member = ProjectMember.objects.get(project=project, user=other_user)
        assert member.role != "owner"
