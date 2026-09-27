from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.offline_sync.models import SyncDevice, SyncOperation
from apps.offline_sync.services import (
    apply_sync_operations,
    get_changes_since,
    register_device,
)
from apps.projects.models import Project
from apps.tasks.models import Task

User = get_user_model()


@pytest.mark.django_db
class TestRegisterDevice:
    def test_create_device(self):
        user = User.objects.create_user(username="os", email="os@os.com", password="pass")
        device = register_device(user, "dev1", "Phone")
        assert device.device_id == "dev1"
        assert device.device_name == "Phone"
        assert device.user == user

    def test_update_device(self):
        user = User.objects.create_user(username="os2", email="os2@os.com", password="pass")
        register_device(user, "dev1", "Phone")
        device = register_device(user, "dev1", "Tablet")
        assert device.device_name == "Tablet"
        assert SyncDevice.objects.count() == 1


@pytest.mark.django_db
class TestApplySyncOperations:
    @pytest.fixture(autouse=True)
    def setup_data(self, db):
        self.user = User.objects.create_user(username="os3", email="os3@os.com", password="pass")
        self.device = register_device(self.user, "dev1", "Phone")

    def test_create_task(self):
        ops = [{
            "op_type": "create",
            "entity_type": "task",
            "entity_id": "uuid-1",
            "payload": {"title": "Offline Task", "priority": 1},
            "client_timestamp": timezone.now(),
            "device_id": "dev1",
        }]
        results = apply_sync_operations(self.user, ops)
        assert results[0]["status"] == "applied"
        assert Task.objects.filter(title="Offline Task", owner=self.user).exists()
        sync_op = SyncOperation.objects.get(entity_id="uuid-1")
        assert sync_op.status == SyncOperation.Status.APPLIED

    def test_update_task(self):
        task = Task.objects.create(owner=self.user, title="Old")
        ops = [{
            "op_type": "update",
            "entity_type": "task",
            "entity_id": "uuid-2",
            "payload": {"id": task.id, "title": "Updated"},
            "base_version": task.version,
            "client_timestamp": timezone.now(),
            "device_id": "dev1",
        }]
        results = apply_sync_operations(self.user, ops)
        assert results[0]["status"] == "applied"
        task.refresh_from_db()
        assert task.title == "Updated"

    def test_update_task_conflict(self):
        task = Task.objects.create(owner=self.user, title="Old")
        task.version = 5
        task.save()
        ops = [{
            "op_type": "update",
            "entity_type": "task",
            "entity_id": "uuid-3",
            "payload": {"id": task.id, "title": "Updated"},
            "base_version": 3,
            "client_timestamp": timezone.now(),
            "device_id": "dev1",
        }]
        results = apply_sync_operations(self.user, ops)
        assert results[0]["status"] == "conflict"
        assert results[0]["conflict"] is True
        sync_op = SyncOperation.objects.get(entity_id="uuid-3")
        assert sync_op.status == SyncOperation.Status.CONFLICT

    def test_update_task_not_found(self):
        ops = [{
            "op_type": "update",
            "entity_type": "task",
            "entity_id": "uuid-4",
            "payload": {"id": 999, "title": "Updated"},
            "base_version": 0,
            "client_timestamp": timezone.now(),
            "device_id": "dev1",
        }]
        results = apply_sync_operations(self.user, ops)
        assert results[0]["status"] == "rejected"
        assert "not found" in results[0]["error"].lower()

    def test_update_task_sin_base_version_rechazada(self):
        """Sin base_version el update se rechaza (no hay detección de conflictos)."""
        task = Task.objects.create(owner=self.user, title="Old")
        ops = [{
            "op_type": "update",
            "entity_type": "task",
            "entity_id": "uuid-4b",
            "payload": {"id": task.id, "title": "Updated"},
            "client_timestamp": timezone.now(),
            "device_id": "dev1",
        }]
        results = apply_sync_operations(self.user, ops)
        assert results[0]["status"] == "rejected"
        assert "base_version" in results[0]["error"]

    def test_delete_task(self):
        task = Task.objects.create(owner=self.user, title="ToDelete")
        ops = [{
            "op_type": "delete",
            "entity_type": "task",
            "entity_id": "uuid-5",
            "payload": {"id": task.id},
            "base_version": task.version,
            "client_timestamp": timezone.now(),
            "device_id": "dev1",
        }]
        results = apply_sync_operations(self.user, ops)
        assert results[0]["status"] == "applied"
        assert not Task.objects.filter(id=task.id).exists()

    def test_delete_task_not_found(self):
        ops = [{
            "op_type": "delete",
            "entity_type": "task",
            "entity_id": "uuid-6",
            "payload": {"id": 999},
            "base_version": 0,
            "client_timestamp": timezone.now(),
            "device_id": "dev1",
        }]
        results = apply_sync_operations(self.user, ops)
        assert results[0]["status"] == "rejected"

    def test_create_project(self):
        ops = [{
            "op_type": "create",
            "entity_type": "project",
            "entity_id": "uuid-7",
            "payload": {"name": "Offline Project"},
            "client_timestamp": timezone.now(),
            "device_id": "dev1",
        }]
        results = apply_sync_operations(self.user, ops)
        assert results[0]["status"] == "applied"
        assert Project.objects.filter(name="Offline Project", owner=self.user).exists()

    def test_unknown_entity_type(self):
        ops = [{
            "op_type": "create",
            "entity_type": "unknown",
            "entity_id": "uuid-8",
            "payload": {},
            "client_timestamp": timezone.now(),
            "device_id": "dev1",
        }]
        results = apply_sync_operations(self.user, ops)
        assert results[0]["status"] == "rejected"
        assert "Unknown entity type" in results[0]["error"]

    def test_operation_error(self):
        ops = [{
            "op_type": "create",
            "entity_type": "task",
            "entity_id": "uuid-9",
            "payload": {"invalid_field": "x"},
            "client_timestamp": timezone.now(),
            "device_id": "dev1",
        }]
        results = apply_sync_operations(self.user, ops)
        assert results[0]["status"] == "applied"  # invalid fields are filtered out


@pytest.mark.django_db
class TestGetChangesSince:
    def test_get_changes(self):
        user = User.objects.create_user(username="os4", email="os4@os.com", password="pass")
        past = timezone.now() - timedelta(days=1)
        task = Task.objects.create(owner=user, title="T")
        Task.objects.filter(id=task.id).update(updated_at=past)
        project = Project.objects.create(owner=user, name="P")
        Project.objects.filter(id=project.id).update(updated_at=past)

        changes = get_changes_since(user, past - timedelta(hours=1))
        assert len(changes["tasks"]) == 1
        assert len(changes["projects"]) == 1
        assert changes["tasks"][0]["title"] == "T"
        assert changes["projects"][0]["name"] == "P"

        changes = get_changes_since(user, past + timedelta(hours=1))
        assert len(changes["tasks"]) == 0
        assert len(changes["projects"]) == 0
