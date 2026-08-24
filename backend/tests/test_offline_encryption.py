"""Tests para offline sync y E2E encryption."""
import pytest
from django.utils import timezone
from datetime import timedelta


# --- Offline Sync ---

@pytest.mark.django_db
class TestOfflineSync:
    def test_register_device(self, authed_client, user):
        resp = authed_client.post("/api/sync/register-device/", {
            "device_id": "device-001",
            "device_name": "iPhone 15",
        }, format="json")
        assert resp.status_code == 201
        assert resp.data["device_id"] == "device-001"

    def test_push_create_task(self, authed_client, user):
        from apps.offline_sync.models import SyncDevice
        SyncDevice.objects.create(user=user, device_id="dev-1")
        resp = authed_client.post("/api/sync/push/", {
            "operations": [
                {
                    "device_id": "dev-1",
                    "op_type": "create",
                    "entity_type": "task",
                    "entity_id": "client-uuid-1",
                    "payload": {"title": "Tarea offline", "priority": 3},
                    "client_timestamp": timezone.now().isoformat(),
                }
            ]
        }, format="json")
        assert resp.status_code == 200
        assert resp.data["results"][0]["status"] == "applied"
        from apps.tasks.models import Task
        assert Task.objects.filter(owner=user, title="Tarea offline").exists()

    def test_push_update_task(self, authed_client, user, task):
        from apps.offline_sync.models import SyncDevice
        SyncDevice.objects.create(user=user, device_id="dev-1")
        resp = authed_client.post("/api/sync/push/", {
            "operations": [
                {
                    "device_id": "dev-1",
                    "op_type": "update",
                    "entity_type": "task",
                    "entity_id": "client-uuid-1",
                    "payload": {"id": task.id, "title": "Updated title"},
                    "client_timestamp": (timezone.now() + timedelta(seconds=10)).isoformat(),
                }
            ]
        }, format="json")
        assert resp.status_code == 200
        assert resp.data["results"][0]["status"] == "applied"
        task.refresh_from_db()
        assert task.title == "Updated title"

    def test_push_delete_task(self, authed_client, user, task):
        from apps.offline_sync.models import SyncDevice
        SyncDevice.objects.create(user=user, device_id="dev-1")
        task_id = task.id
        resp = authed_client.post("/api/sync/push/", {
            "operations": [
                {
                    "device_id": "dev-1",
                    "op_type": "delete",
                    "entity_type": "task",
                    "entity_id": "client-uuid-1",
                    "payload": {"id": task_id},
                    "client_timestamp": timezone.now().isoformat(),
                }
            ]
        }, format="json")
        assert resp.status_code == 200
        assert resp.data["results"][0]["status"] == "applied"
        from apps.tasks.models import Task
        assert not Task.objects.filter(id=task_id).exists()

    def test_pull_changes(self, authed_client, user, task):
        resp = authed_client.get(f"/api/sync/pull/?since={(timezone.now() - timedelta(days=1)).isoformat()}")
        assert resp.status_code == 200
        assert "tasks" in resp.data
        assert len(resp.data["tasks"]) >= 1


# --- E2E Encryption ---

@pytest.mark.django_db
class TestEncryption:
    def test_register_public_key(self, authed_client, user):
        resp = authed_client.post("/api/public-keys/", {
            "public_key": "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...",
            "key_id": "key-001",
            "algorithm": "RSA-OA-256",
        }, format="json")
        assert resp.status_code == 201
        from apps.encryption.models import UserPublicKey
        assert UserPublicKey.objects.filter(user=user, key_id="key-001").exists()

    def test_get_active_key(self, authed_client, user):
        from apps.encryption.models import UserPublicKey
        UserPublicKey.objects.create(
            user=user, public_key="abc", key_id="k1", is_active=True,
        )
        resp = authed_client.get("/api/public-keys/active/")
        assert resp.status_code == 200
        assert resp.data["key_id"] == "k1"

    def test_create_encrypted_task(self, authed_client, user):
        resp = authed_client.post("/api/encrypted-tasks/", {
            "encrypted_data": "U2FsdGVkX1+...",
            "encryption_key_id": "key-001",
            "iv": "dGhpcyBpcyBhIGl2",
            "auth_tag": "dGhpcyBpcyBhIHRhZw==",
            "algorithm": "AES-256-GCM",
        }, format="json")
        assert resp.status_code == 201
        from apps.encryption.models import EncryptedTask
        assert EncryptedTask.objects.filter(owner=user).exists()

    def test_list_encrypted_tasks(self, authed_client, user):
        from apps.encryption.models import EncryptedTask
        EncryptedTask.objects.create(
            owner=user, encrypted_data="data", encryption_key_id="k1", iv="iv",
        )
        resp = authed_client.get("/api/encrypted-tasks/")
        assert resp.status_code == 200
        data = resp.data["results"] if "results" in resp.data else resp.data
        assert len(data) == 1

    def test_share_encrypted_task(self, authed_client, user, other_user):
        from apps.encryption.models import EncryptedTask, UserPublicKey
        task = EncryptedTask.objects.create(
            owner=user, encrypted_data="data", encryption_key_id="k1", iv="iv",
        )
        pk = UserPublicKey.objects.create(
            user=other_user, public_key="pubkey2", key_id="key-user2", is_active=True,
        )
        resp = authed_client.post(f"/api/encrypted-tasks/{task.id}/share/", {
            "user_email": other_user.email,
            "encrypted_key": "encrypted_aes_key_for_user2",
            "public_key_id": pk.id,
        }, format="json")
        assert resp.status_code == 201
        from apps.encryption.models import EncryptedKeyShare
        assert EncryptedKeyShare.objects.filter(encrypted_task=task, user=other_user).exists()

    def test_list_shared_tasks(self, authed_client, user, other_user):
        from apps.encryption.models import EncryptedTask, UserPublicKey, EncryptedKeyShare
        # other_user crea una tarea y la comparte con user
        task = EncryptedTask.objects.create(
            owner=other_user, encrypted_data="secret", encryption_key_id="k1", iv="iv",
        )
        pk = UserPublicKey.objects.create(
            user=user, public_key="pubkey_user", key_id="key-user", is_active=True,
        )
        EncryptedKeyShare.objects.create(
            encrypted_task=task, user=user, encrypted_key="enc_key", user_public_key=pk,
        )
        resp = authed_client.get("/api/encrypted-tasks/shared/")
        assert resp.status_code == 200
        assert len(resp.data) == 1
        assert resp.data[0]["encrypted_data"] == "secret"
