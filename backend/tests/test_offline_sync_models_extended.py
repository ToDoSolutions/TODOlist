"""Tests exhaustivos para modelos de offline_sync."""
import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.utils import timezone

from apps.offline_sync.models import SyncDevice, SyncOperation

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="os", email="os@os.com", password="pass")


@pytest.fixture
def device(user, db):
    return SyncDevice.objects.create(user=user, device_id="dev-123")


@pytest.mark.django_db
class TestSyncDevice:
    def test_str(self, user, device):
        assert user.email in str(device)
        assert "dev-123" in str(device)

    def test_defaults(self, user, device):
        assert device.device_name == ""
        assert device.last_sync_at is None
        assert device.is_active is True

    def test_unique_device_id(self, user):
        SyncDevice.objects.create(user=user, device_id="dev-123")
        with pytest.raises(IntegrityError):
            SyncDevice.objects.create(user=user, device_id="dev-123")


@pytest.mark.django_db
class TestSyncOperation:
    def test_str(self, user, device):
        op = SyncOperation.objects.create(
            device=device, user=user, op_type="create", entity_type="task",
            entity_id="uuid-1", client_timestamp=timezone.now()
        )
        assert "create" in str(op)
        assert "task" in str(op)
        assert "pending" in str(op)

    def test_op_type_choices(self):
        assert SyncOperation.OpType.CREATE == "create"
        assert SyncOperation.OpType.UPDATE == "update"
        assert SyncOperation.OpType.DELETE == "delete"

    def test_status_choices(self):
        assert SyncOperation.Status.PENDING == "pending"
        assert SyncOperation.Status.APPLIED == "applied"
        assert SyncOperation.Status.CONFLICT == "conflict"
        assert SyncOperation.Status.REJECTED == "rejected"

    def test_conflict_status_choices(self):
        assert SyncOperation.ConflictStatus.NONE == "none"
        assert SyncOperation.ConflictStatus.CONFLICT == "conflict"
        assert SyncOperation.ConflictStatus.RESOLVED == "resolved"

    def test_defaults(self, user, device):
        op = SyncOperation.objects.create(
            device=device, user=user, op_type="create", entity_type="task",
            entity_id="uuid-1", client_timestamp=timezone.now()
        )
        assert op.server_entity_id is None
        assert op.payload == {}
        assert op.server_timestamp is None
        assert op.status == "pending"
        assert op.conflict_status == "none"
        assert op.base_version is None
        assert op.conflict_data is None
        assert op.applied_at is None

    def test_ordering(self, user, device):
        op1 = SyncOperation.objects.create(
            device=device, user=user, op_type="create", entity_type="task",
            entity_id="uuid-1", client_timestamp=timezone.now()
        )
        op2 = SyncOperation.objects.create(
            device=device, user=user, op_type="update", entity_type="task",
            entity_id="uuid-2", client_timestamp=timezone.now()
        )
        from django.utils import timezone as _tz
        SyncOperation.objects.filter(pk=op1.pk).update(created_at=_tz.now() - _tz.timedelta(hours=1))
        ops = list(SyncOperation.objects.all())
        assert ops[0] == op2  # ordering by -created_at
