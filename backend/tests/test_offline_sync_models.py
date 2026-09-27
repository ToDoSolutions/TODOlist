import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.utils import timezone

from apps.offline_sync.models import SyncDevice, SyncOperation

User = get_user_model()


@pytest.mark.django_db
class TestSyncDevice:
    @pytest.fixture(autouse=True)
    def setup_data(self, db):
        self.user = User.objects.create_user(username="osm", email="osm@osm.com", password="pass")

    def test_str(self):
        d = SyncDevice.objects.create(user=self.user, device_id="d1", device_name="Phone")
        assert "osm@osm.com" in str(d)
        assert "d1" in str(d)

    def test_defaults(self):
        d = SyncDevice.objects.create(user=self.user, device_id="d1")
        assert d.device_name == ""
        assert d.is_active is True
        assert d.last_sync_at is None

    def test_unique_device_id(self):
        SyncDevice.objects.create(user=self.user, device_id="d1")
        with pytest.raises(IntegrityError):
            SyncDevice.objects.create(user=self.user, device_id="d1")


@pytest.mark.django_db
class TestSyncOperation:
    @pytest.fixture(autouse=True)
    def setup_data(self, db):
        self.user = User.objects.create_user(username="osm2", email="osm2@osm.com", password="pass")
        self.device = SyncDevice.objects.create(user=self.user, device_id="d1")

    def test_str(self):
        op = SyncOperation.objects.create(
            device=self.device, user=self.user, op_type="create", entity_type="task",
            entity_id="e1", client_timestamp=timezone.now(),
        )
        assert "create" in str(op)
        assert "task" in str(op)
        assert "pending" in str(op)

    def test_choices(self):
        assert SyncOperation.OpType.CREATE == "create"
        assert SyncOperation.OpType.UPDATE == "update"
        assert SyncOperation.OpType.DELETE == "delete"
        assert SyncOperation.Status.PENDING == "pending"
        assert SyncOperation.Status.APPLIED == "applied"
        assert SyncOperation.Status.CONFLICT == "conflict"
        assert SyncOperation.Status.REJECTED == "rejected"
        assert SyncOperation.ConflictStatus.NONE == "none"
        assert SyncOperation.ConflictStatus.CONFLICT == "conflict"
        assert SyncOperation.ConflictStatus.RESOLVED == "resolved"

    def test_defaults(self):
        op = SyncOperation.objects.create(
            device=self.device, user=self.user, op_type="create", entity_type="task",
            entity_id="e1", client_timestamp=timezone.now(),
        )
        assert op.status == "pending"
        assert op.conflict_status == "none"
        assert op.payload == {}
        assert op.base_version is None
        assert op.conflict_data is None
