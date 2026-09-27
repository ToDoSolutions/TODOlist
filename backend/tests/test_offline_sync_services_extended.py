"""Tests exhaustivos para offline_sync/services.py."""
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.offline_sync.models import SyncDevice
from apps.offline_sync.services import (
    apply_sync_operations,
    get_changes_since,
    register_device,
)
from apps.projects.models import Project
from apps.tasks.models import Task

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="os", email="os@os.com", password="pass")


@pytest.fixture
def device(user):
    return register_device(user, "dev-1", "Test Device")


@pytest.mark.django_db
class TestRegisterDevice:
    def test_create(self, user):
        device = register_device(user, "dev-1", "Phone")
        assert device.device_id == "dev-1"
        assert device.device_name == "Phone"
        assert device.user == user

    def test_update_existing(self, user):
        register_device(user, "dev-1", "Phone")
        device = register_device(user, "dev-1", "Tablet")
        assert device.device_name == "Tablet"
        assert SyncDevice.objects.filter(device_id="dev-1").count() == 1


@pytest.mark.django_db
class TestApplySyncOperations:
    def test_create_task(self, user, device):
        ops = [{
            "op_type": "create", "entity_type": "task", "entity_id": "c-1",
            "payload": {"title": "Offline Task", "priority": 1},
            "client_timestamp": timezone.now().isoformat(),
            "device_id": "dev-1",
        }]
        results = apply_sync_operations(user, ops)
        assert results[0]["status"] == "applied"
        assert Task.objects.filter(title="Offline Task").exists()

    def test_update_task(self, user, device):
        task = Task.objects.create(owner=user, title="Old")
        ops = [{
            "op_type": "update", "entity_type": "task", "entity_id": "c-1",
            "payload": {"id": task.id, "title": "New"},
            "base_version": task.version,
            "client_timestamp": timezone.now().isoformat(),
            "device_id": "dev-1",
        }]
        results = apply_sync_operations(user, ops)
        assert results[0]["status"] == "applied"
        task.refresh_from_db()
        assert task.title == "New"

    def test_update_task_conflict(self, user, device):
        task = Task.objects.create(owner=user, title="Old")
        task.version = 5
        task.save(increment_version=False)
        ops = [{
            "op_type": "update", "entity_type": "task", "entity_id": "c-1",
            "payload": {"id": task.id, "title": "New"},
            "client_timestamp": timezone.now().isoformat(),
            "base_version": 2,
            "device_id": "dev-1",
        }]
        results = apply_sync_operations(user, ops)
        assert results[0]["status"] == "conflict"
        assert results[0]["conflict"] is True

    def test_update_task_not_found(self, user, device):
        ops = [{
            "op_type": "update", "entity_type": "task", "entity_id": "c-1",
            "payload": {"id": 999, "title": "New"},
            "base_version": 0,
            "client_timestamp": timezone.now().isoformat(),
            "device_id": "dev-1",
        }]
        results = apply_sync_operations(user, ops)
        assert results[0]["status"] == "rejected"

    def test_delete_task(self, user, device):
        task = Task.objects.create(owner=user, title="ToDelete")
        ops = [{
            "op_type": "delete", "entity_type": "task", "entity_id": "c-1",
            "payload": {"id": task.id},
            "base_version": task.version,
            "client_timestamp": timezone.now().isoformat(),
            "device_id": "dev-1",
        }]
        results = apply_sync_operations(user, ops)
        assert results[0]["status"] == "applied"
        assert not Task.objects.filter(id=task.id).exists()

    def test_create_project(self, user, device):
        ops = [{
            "op_type": "create", "entity_type": "project", "entity_id": "c-2",
            "payload": {"name": "Offline Project"},
            "client_timestamp": timezone.now().isoformat(),
            "device_id": "dev-1",
        }]
        results = apply_sync_operations(user, ops)
        assert results[0]["status"] == "applied"
        assert Project.objects.filter(name="Offline Project").exists()

    def test_update_project(self, user, device):
        project = Project.objects.create(owner=user, name="Old")
        ops = [{
            "op_type": "update", "entity_type": "project", "entity_id": "c-2",
            "payload": {"id": project.id, "name": "New"},
            "client_timestamp": timezone.now().isoformat(),
            "device_id": "dev-1",
        }]
        results = apply_sync_operations(user, ops)
        assert results[0]["status"] == "applied"
        project.refresh_from_db()
        assert project.name == "New"

    def test_delete_project(self, user, device):
        project = Project.objects.create(owner=user, name="ToDelete")
        ops = [{
            "op_type": "delete", "entity_type": "project", "entity_id": "c-2",
            "payload": {"id": project.id},
            "client_timestamp": timezone.now().isoformat(),
            "device_id": "dev-1",
        }]
        results = apply_sync_operations(user, ops)
        assert results[0]["status"] == "applied"
        assert not Project.objects.filter(id=project.id).exists()

    def test_unknown_entity_type(self, user, device):
        ops = [{
            "op_type": "create", "entity_type": "unknown", "entity_id": "c-1",
            "payload": {},
            "client_timestamp": timezone.now().isoformat(),
            "device_id": "dev-1",
        }]
        results = apply_sync_operations(user, ops)
        assert results[0]["status"] == "rejected"

    def test_filters_disallowed_fields(self, user, device):
        """Verifica que solo se aplican campos permitidos."""
        ops = [{
            "op_type": "create", "entity_type": "task", "entity_id": "c-1",
            "payload": {"title": "Task", "owner": 999, "id": 999},
            "client_timestamp": timezone.now().isoformat(),
            "device_id": "dev-1",
        }]
        results = apply_sync_operations(user, ops)
        assert results[0]["status"] == "applied"
        task = Task.objects.get(title="Task")
        assert task.owner == user  # owner no se sobreescribe desde payload


@pytest.mark.django_db
class TestGetChangesSince:
    def test_empty(self, user):
        result = get_changes_since(user, timezone.now())
        assert result["tasks"] == []
        assert result["projects"] == []

    def test_returns_updated(self, user):
        Task.objects.create(owner=user, title="Task")
        Project.objects.create(owner=user, name="Project")
        result = get_changes_since(user, timezone.now() - timezone.timedelta(hours=1))
        assert len(result["tasks"]) == 1
        assert len(result["projects"]) == 1
        assert result["tasks"][0]["title"] == "Task"
