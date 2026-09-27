import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.offline_sync.models import SyncDevice, SyncOperation

User = get_user_model()


@pytest.fixture
def auth_client(db):
    user = User.objects.create_user(username="osv", email="osv@osv.com", password="pass")
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return client, user


@pytest.mark.django_db
class TestSyncDeviceViewSet:
    def test_list_devices(self, auth_client):
        client, user = auth_client
        SyncDevice.objects.create(user=user, device_id="d1", device_name="Phone")
        resp = client.get("/api/sync/devices/")
        assert resp.status_code == 200
        assert len(resp.data) == 1

    def test_retrieve_device(self, auth_client):
        client, user = auth_client
        device = SyncDevice.objects.create(user=user, device_id="d1", device_name="Phone")
        resp = client.get(f"/api/sync/devices/{device.device_id}/")
        assert resp.status_code == 200
        assert resp.data["device_id"] == "d1"

    def test_revoke_device(self, auth_client):
        client, user = auth_client
        device = SyncDevice.objects.create(user=user, device_id="d1", device_name="Phone", is_active=True)
        resp = client.post(f"/api/sync/devices/{device.device_id}/revoke/")
        assert resp.status_code == 200
        device.refresh_from_db()
        assert device.is_active is False

    def test_destroy_device(self, auth_client):
        client, user = auth_client
        device = SyncDevice.objects.create(user=user, device_id="d1", device_name="Phone")
        resp = client.delete(f"/api/sync/devices/{device.device_id}/")
        assert resp.status_code == 204
        assert not SyncDevice.objects.filter(id=device.id).exists()


@pytest.mark.django_db
class TestSyncViews:
    def test_register_device(self, auth_client):
        client, user = auth_client
        resp = client.post("/api/sync/register-device/", {"device_id": "d1", "device_name": "Phone"})
        assert resp.status_code == 201
        assert SyncDevice.objects.filter(user=user, device_id="d1").exists()

    def test_push_changes(self, auth_client):
        client, _ = auth_client
        resp = client.post("/api/sync/push/", {"operations": []})
        assert resp.status_code == 200
        assert resp.data["results"] == []

    def test_pull_changes(self, auth_client):
        client, user = auth_client
        SyncDevice.objects.create(user=user, device_id="d1", device_name="Phone")
        resp = client.get("/api/sync/pull/?device_id=d1")
        assert resp.status_code == 200
        assert "tasks" in resp.data
        assert "projects" in resp.data
        device = SyncDevice.objects.get(device_id="d1")
        assert device.last_sync_at is not None

    def test_pull_changes_since(self, auth_client):
        client, _ = auth_client
        resp = client.get("/api/sync/pull/?since=2024-01-01T00:00:00Z")
        assert resp.status_code == 200
        assert "tasks" in resp.data

    def test_list_operations(self, auth_client):
        client, user = auth_client
        device = SyncDevice.objects.create(user=user, device_id="d1", device_name="Phone")
        SyncOperation.objects.create(user=user, device=device, op_type="create", entity_type="task", entity_id="e1", payload={}, client_timestamp=timezone.now())
        resp = client.get("/api/sync/operations/")
        assert resp.status_code == 200
        assert len(resp.data) == 1


@pytest.mark.django_db
class TestRevokeAll:
    """POST /api/sync/devices/revoke_all/ — logout masivo de dispositivos."""

    def test_revoke_all_desactiva_todos(self, auth_client):
        client, user = auth_client
        SyncDevice.objects.create(user=user, device_id="d1", is_active=True)
        SyncDevice.objects.create(user=user, device_id="d2", is_active=True)
        SyncDevice.objects.create(user=user, device_id="d3", is_active=False)
        resp = client.post("/api/sync/devices/revoke_all/")
        assert resp.status_code == 200
        assert resp.json()["revoked"] == 2
        assert not SyncDevice.objects.filter(user=user, is_active=True).exists()

    def test_revoke_all_no_toca_ajenos(self, auth_client):
        client, user = auth_client  # user necesario para el SyncDevice propio
        other, _ = User.objects.get_or_create(
            username="osv_o", defaults={"email": "osv_o@x.com"}
        )
        SyncDevice.objects.create(user=user, device_id="mio")
        SyncDevice.objects.create(user=other, device_id="suyo")
        resp = client.post("/api/sync/devices/revoke_all/")
        assert resp.status_code == 200
        assert SyncDevice.objects.get(user=other).is_active is True

    def test_revoke_all_sin_devices(self, auth_client):
        client, _user = auth_client
        resp = client.post("/api/sync/devices/revoke_all/")
        assert resp.status_code == 200
        assert resp.json()["revoked"] == 0

    def test_revoke_all_tras_revocar_push_rechazado(self, auth_client):
        client, user = auth_client
        SyncDevice.objects.create(user=user, device_id="d1", is_active=True)
        client.post("/api/sync/devices/revoke_all/")
        resp = client.post("/api/sync/push/", {
            "operations": [{
                "op_type": "create", "entity_type": "task",
                "entity_id": "e1", "payload": {"title": "x"},
                "device_id": "d1",
            }]
        }, format="json")
        assert resp.status_code == 403
