"""Tests de borde para offline_sync/services: límites, hijacking, field filtering."""
import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied

from apps.offline_sync.models import SyncDevice
from apps.offline_sync.services import (
    MAX_SYNC_OPERATIONS,
    apply_sync_operations,
    get_changes_since,
    register_device,
)
from apps.projects.models import Project
from apps.tasks.models import Task

User = get_user_model()


@pytest.fixture
def user(db):
    u, _ = User.objects.get_or_create(
        username="os_e", defaults={"email": "os_e@x.com"}
    )
    return u


@pytest.fixture
def device(user):
    return SyncDevice.objects.create(user=user, device_id="dev-e", is_active=True)


def _op(op_type="create", entity_type="task", entity_id="e1",
        payload=None, device_id="dev-e", base_version=None):
    from django.utils import timezone as _tz
    op = {
        "op_type": op_type,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "payload": payload or {},
        "device_id": device_id,
        "client_timestamp": _tz.now(),
    }
    if base_version is not None:
        op["base_version"] = base_version
    return op


@pytest.mark.django_db
class TestRegisterDevice:
    def test_hijack_otro_usuario_denied(self, user):
        other, _ = User.objects.get_or_create(
            username="os_o", defaults={"email": "os_o@x.com"}
        )
        SyncDevice.objects.create(user=other, device_id="dev-ajeno")
        with pytest.raises(PermissionDenied):
            register_device(user, "dev-ajeno", "Mi Phone")

    def test_reactiva_dispositivo_inactivo(self, user):
        SyncDevice.objects.create(
            user=user, device_id="dev-i", is_active=False
        )
        d = register_device(user, "dev-i")
        assert d.is_active is True

    def test_nombre_vacio_conserva_anterior(self, user):
        SyncDevice.objects.create(
            user=user, device_id="dev-n", device_name="Phone"
        )
        d = register_device(user, "dev-n", "")
        assert d.device_name == "Phone"


@pytest.mark.django_db
class TestPushLimits:
    def test_no_lista_rechazada(self, user):
        with pytest.raises(ValueError):
            apply_sync_operations(user, "no-es-lista")
        with pytest.raises(ValueError):
            apply_sync_operations(user, {"op": 1})
        with pytest.raises(ValueError):
            apply_sync_operations(user, None)

    def test_max_operaciones(self, user):
        ops = [_op(entity_id=f"e{i}") for i in range(MAX_SYNC_OPERATIONS + 1)]
        with pytest.raises(ValueError):
            apply_sync_operations(user, ops)

    def test_exactamente_max_ok(self, user, device):
        ops = [_op(entity_id=f"e{i}") for i in range(MAX_SYNC_OPERATIONS)]
        results = apply_sync_operations(user, ops)
        assert len(results) == MAX_SYNC_OPERATIONS

    def test_device_ajeno_rechazado(self, user):
        other, _ = User.objects.get_or_create(
            username="os_o2", defaults={"email": "os_o2@x.com"}
        )
        SyncDevice.objects.create(
            user=other, device_id="dev-otro", is_active=True
        )
        with pytest.raises(PermissionDenied):
            apply_sync_operations(user, [_op(device_id="dev-otro")])

    def test_device_revocado_rechazado(self, user):
        SyncDevice.objects.create(
            user=user, device_id="dev-rev", is_active=False
        )
        with pytest.raises(PermissionDenied):
            apply_sync_operations(user, [_op(device_id="dev-rev")])

    def test_sin_device_id_rechazado(self, user):
        """SyncOperation.device es NOT NULL: sin device no puede registrarse."""
        op = _op(payload={"title": "x"})
        del op["device_id"]
        results = apply_sync_operations(user, [op])
        assert results[0]["status"] == "rejected"


@pytest.mark.django_db
class TestFieldFiltering:
    """El payload no puede inyectar campos fuera del whitelist."""

    def test_owner_no_inyectable_en_create(self, user, device):
        other, _ = User.objects.get_or_create(
            username="os_o3", defaults={"email": "os_o3@x.com"}
        )
        results = apply_sync_operations(user, [
            _op(payload={"title": "t", "owner": other.id})
        ])
        assert results[0]["status"] == "applied"
        t = Task.objects.get(title="t")
        assert t.owner_id == user.id

    def test_version_no_inyectable(self, user, device):
        results = apply_sync_operations(user, [
            _op(payload={"title": "t", "version": 999})
        ])
        assert results[0]["status"] == "applied"
        t = Task.objects.get(title="t")
        assert t.version != 999

    def test_campos_no_permitidos_ignorados(self, user, device):
        results = apply_sync_operations(user, [
            _op(payload={
                "title": "t", "completed_at": "2020-01-01",
                "assignee": 1, "project": 1, "id": 99999,
            })
        ])
        assert results[0]["status"] == "applied"
        t = Task.objects.get(title="t")
        assert t.id != 99999

    def test_campos_permitidos_aplicados(self, user, device):
        results = apply_sync_operations(user, [
            _op(payload={
                "title": "t", "description": "d", "priority": 1,
                "state": "in_progress", "story_points": 5,
            })
        ])
        assert results[0]["status"] == "applied"
        t = Task.objects.get(title="t")
        assert t.priority == 1 and t.story_points == 5


@pytest.mark.django_db
class TestConflictEdges:
    def test_update_sin_base_version_rechazado(self, user, device):
        t = Task.objects.create(owner=user, title="t")
        results = apply_sync_operations(user, [
            _op("update", payload={"id": t.id, "title": "n"})
        ])
        assert results[0]["status"] == "rejected"
        assert "base_version" in results[0]["error"]

    def test_update_conflicto_version(self, user, device):
        t = Task.objects.create(owner=user, title="t")
        t.title = "v2"
        t.save()  # version++
        t.refresh_from_db()
        results = apply_sync_operations(user, [
            _op("update", payload={"id": t.id, "title": "stale"},
                base_version=t.version - 1)
        ])
        assert results[0]["status"] == "conflict"
        assert results[0]["current_version"] == t.version
        t.refresh_from_db()
        assert t.title == "v2"  # server wins

    def test_update_sin_conflicto_aplica(self, user, device):
        t = Task.objects.create(owner=user, title="t")
        t.refresh_from_db()
        results = apply_sync_operations(user, [
            _op("update", payload={"id": t.id, "title": "nuevo"},
                base_version=t.version)
        ])
        assert results[0]["status"] == "applied"
        t.refresh_from_db()
        assert t.title == "nuevo"

    def test_update_tarea_ajena_rechazada(self, user, device):
        other, _ = User.objects.get_or_create(
            username="os_o4", defaults={"email": "os_o4@x.com"}
        )
        t = Task.objects.create(owner=other, title="ajena")
        t.refresh_from_db()
        results = apply_sync_operations(user, [
            _op("update", payload={"id": t.id, "title": "h"},
                base_version=t.version)
        ])
        assert results[0]["status"] == "rejected"
        t.refresh_from_db()
        assert t.title == "ajena"

    def test_delete_conflicto_version(self, user, device):
        t = Task.objects.create(owner=user, title="t")
        t.title = "v2"
        t.save()
        t.refresh_from_db()
        results = apply_sync_operations(user, [
            _op("delete", payload={"id": t.id}, base_version=t.version - 1)
        ])
        assert results[0]["status"] == "conflict"
        assert Task.objects.filter(pk=t.pk).exists()

    def test_delete_sin_conflicto_aplica(self, user, device):
        t = Task.objects.create(owner=user, title="t")
        t.refresh_from_db()
        results = apply_sync_operations(user, [
            _op("delete", payload={"id": t.id}, base_version=t.version)
        ])
        assert results[0]["status"] == "applied"
        assert not Task.objects.filter(pk=t.pk).exists()

    def test_delete_tarea_ajena_rechazada(self, user, device):
        other, _ = User.objects.get_or_create(
            username="os_o5", defaults={"email": "os_o5@x.com"}
        )
        t = Task.objects.create(owner=other, title="ajena")
        t.refresh_from_db()
        results = apply_sync_operations(user, [
            _op("delete", payload={"id": t.id}, base_version=t.version)
        ])
        assert results[0]["status"] == "rejected"
        assert Task.objects.filter(pk=t.pk).exists()

    def test_entity_desconocido_rechazado(self, user, device):
        results = apply_sync_operations(user, [
            _op(entity_type="comment")
        ])
        assert results[0]["status"] == "rejected"
        assert "Unknown entity" in results[0]["error"]

    def test_op_fallida_no_aborta_lote(self, user, device):
        results = apply_sync_operations(user, [
            _op(entity_id="ok", payload={"title": "bien"}),
            {"entity_id": "mala"},  # falta op_type → excepción
            _op(entity_id="ok2", payload={"title": "bien2"}),
        ])
        assert results[0]["status"] == "applied"
        assert results[1]["status"] == "rejected"
        assert results[2]["status"] == "applied"


@pytest.mark.django_db
class TestProjectOps:
    def test_create_project(self, user, device):
        results = apply_sync_operations(user, [
            _op(entity_type="project", payload={"name": "P", "color": "#fff"})
        ])
        assert results[0]["status"] == "applied"
        assert Project.objects.filter(name="P", owner=user).exists()

    def test_update_project_ajeno_rechazado(self, user, device):
        other, _ = User.objects.get_or_create(
            username="os_o6", defaults={"email": "os_o6@x.com"}
        )
        p = Project.objects.create(owner=other, name="Ajeno")
        results = apply_sync_operations(user, [
            _op("update", entity_type="project",
                payload={"id": p.id, "name": "hack"})
        ])
        assert results[0]["status"] == "rejected"
        p.refresh_from_db()
        assert p.name == "Ajeno"

    def test_delete_project_ajeno_rechazado(self, user, device):
        other, _ = User.objects.get_or_create(
            username="os_o7", defaults={"email": "os_o7@x.com"}
        )
        p = Project.objects.create(owner=other, name="Ajeno")
        results = apply_sync_operations(user, [
            _op("delete", entity_type="project", payload={"id": p.id})
        ])
        assert results[0]["status"] == "rejected"
        assert Project.objects.filter(pk=p.pk).exists()

    def test_update_project_propio(self, user, device):
        p = Project.objects.create(owner=user, name="P")
        results = apply_sync_operations(user, [
            _op("update", entity_type="project",
                payload={"id": p.id, "name": "P2", "is_archived": True})
        ])
        assert results[0]["status"] == "applied"
        p.refresh_from_db()
        assert p.name == "P2" and p.is_archived

    def test_project_owner_no_inyectable(self, user, device):
        other, _ = User.objects.get_or_create(
            username="os_o8", defaults={"email": "os_o8@x.com"}
        )
        apply_sync_operations(user, [
            _op(entity_type="project",
                payload={"name": "P", "owner": other.id})
        ])
        assert Project.objects.get(name="P").owner_id == user.id


@pytest.mark.django_db
class TestGetChangesSince:
    def test_solo_cambios_posteriores(self, user):
        from django.utils import timezone
        old = Task.objects.create(owner=user, title="old")
        Task.objects.filter(pk=old.pk).update(
            updated_at=timezone.now() - __import__("datetime").timedelta(days=10)
        )
        Task.objects.create(owner=user, title="new")
        since = timezone.now() - __import__("datetime").timedelta(days=1)
        r = get_changes_since(user, since)
        titles = [t["title"] for t in r["tasks"]]
        assert "new" in titles and "old" not in titles

    def test_incluye_projects(self, user):
        from django.utils import timezone
        Project.objects.create(owner=user, name="P")
        r = get_changes_since(
            user, timezone.now() - __import__("datetime").timedelta(hours=1)
        )
        assert any(p["name"] == "P" for p in r["projects"])

    def test_no_expone_ajenos(self, user):
        from django.utils import timezone
        other, _ = User.objects.get_or_create(
            username="os_o9", defaults={"email": "os_o9@x.com"}
        )
        Task.objects.create(owner=other, title="ajena")
        r = get_changes_since(
            user, timezone.now() - __import__("datetime").timedelta(hours=1)
        )
        assert all(t["title"] != "ajena" for t in r["tasks"])

    def test_task_to_dict_campos(self, user):
        from django.utils import timezone
        t = Task.objects.create(owner=user, title="t", priority=2)
        r = get_changes_since(
            user, timezone.now() - __import__("datetime").timedelta(hours=1)
        )
        d = next(x for x in r["tasks"] if x["id"] == t.id)
        assert d["title"] == "t"
        assert d["priority"] == 2
        assert "version" in d
        assert "updated_at" in d
