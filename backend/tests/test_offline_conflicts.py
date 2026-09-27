"""Demostración formal de la semántica de resolución de conflictos offline.

Política documentada (ver docs/ARCHITECTURE.md §4):
- Optimistic locking por `Task.version` (base_version del cliente vs servidor).
- Server-wins: en conflicto el servidor conserva su estado y devuelve
  `server_data` para que el cliente reconcilie (merge o reintento).
- Sin `base_version` → rejected (no hay forma de detectar conflicto).
- `select_for_update` serializa operaciones concurrentes sobre la misma tarea.
- Projects: NO tienen version → update/delete aplican sin detección
  (limitación documentada).
"""
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.offline_sync.models import SyncDevice, SyncOperation
from apps.offline_sync.services import apply_sync_operations
from apps.tasks.models import Task

User = get_user_model()


def _user(name="conf_u"):
    u, _ = User.objects.get_or_create(
        username=name, defaults={"email": f"{name}@x.com"}
    )
    return u


def _device(user, device_id):
    d, _ = SyncDevice.objects.get_or_create(
        user=user, device_id=device_id, defaults={"is_active": True}
    )
    if not d.is_active:
        d.is_active = True
        d.save(update_fields=["is_active"])
    return d


def _op(device_id, op_type, entity_id, payload, base_version=None):
    return {
        "op_type": op_type,
        "entity_type": "task",
        "entity_id": entity_id,
        "payload": payload,
        "device_id": device_id,
        "client_timestamp": timezone.now().isoformat(),
        "base_version": base_version,
    }


@pytest.mark.django_db
class TestConflictSemantics:
    def test_dos_devices_misma_base_version_segundo_conflicta(self):
        """Escenario central: dos dispositivos editan offline la misma tarea
        con la misma base_version. El primero gana; el segundo recibe
        conflicto con server_data para reconciliar."""
        user = _user()
        _device(user, "phone")
        _device(user, "laptop")
        task = Task.objects.create(owner=user, title="Original", priority=3)
        v0 = task.version

        # Phone edita offline con base v0 → aplica y sube a v0+1
        r1 = apply_sync_operations(user, [_op(
            "phone", "update", "c1", {"id": task.id, "title": "Phone"}, v0
        )])
        assert r1[0]["status"] == "applied"
        task.refresh_from_db()
        assert task.title == "Phone"
        assert task.version == v0 + 1

        # Laptop edita offline con la MISMA base v0 (obsoleta) → conflicto
        r2 = apply_sync_operations(user, [_op(
            "laptop", "update", "c2",
            {"id": task.id, "title": "Laptop"}, v0
        )])
        assert r2[0]["status"] == "conflict"
        assert r2[0]["client_version"] == v0
        assert r2[0]["current_version"] == task.version
        # server_data permite merge/reconciliación en cliente
        assert r2[0]["server_data"]["title"] == "Phone"
        task.refresh_from_db()
        assert task.title == "Phone"  # server-wins

    def test_reintento_tras_conflicto_con_nueva_base_aplica(self):
        """Flujo de reconciliación: conflicto → cliente acepta server_version
        y reintenta → aplica."""
        user = _user()
        _device(user, "d")
        task = Task.objects.create(owner=user, title="A")
        apply_sync_operations(user, [_op(
            "d", "update", "c1", {"id": task.id, "title": "B"}, task.version
        )])
        task.refresh_from_db()

        r_conflict = apply_sync_operations(user, [_op(
            "d", "update", "c2", {"id": task.id, "title": "C"}, 1
        )])
        assert r_conflict[0]["status"] == "conflict"

        r_retry = apply_sync_operations(user, [_op(
            "d", "update", "c3",
            {"id": task.id, "title": "C"},
            r_conflict[0]["current_version"],
        )])
        assert r_retry[0]["status"] == "applied"
        task.refresh_from_db()
        assert task.title == "C"

    def test_campos_distintos_last_write_wins_por_campo(self):
        """Dos ediciones sobre campos DISTINTOS con versión fresca:
        ambas aplican (last-write-wins a nivel de campo)."""
        user = _user()
        _device(user, "d")
        task = Task.objects.create(owner=user, title="T", priority=1,
                                   state="pending")

        apply_sync_operations(user, [_op(
            "d", "update", "c1", {"id": task.id, "priority": 5}, task.version
        )])
        task.refresh_from_db()
        apply_sync_operations(user, [_op(
            "d", "update", "c2", {"id": task.id, "state": "in_progress"},
            task.version,
        )])
        task.refresh_from_db()
        assert task.priority == 5 and task.state == "in_progress"

    def test_delete_vs_update_stale_update_rechazada(self):
        """Delete con versión fresca gana; update posterior sobre tarea
        borrada → rejected (not found), no resurrección."""
        user = _user()
        _device(user, "d1")
        _device(user, "d2")
        task = Task.objects.create(owner=user, title="T")
        v = task.version

        r_del = apply_sync_operations(user, [_op(
            "d1", "delete", "c1", {"id": task.id}, v
        )])
        assert r_del[0]["status"] == "applied"
        assert not Task.objects.filter(id=task.id).exists()

        r_upd = apply_sync_operations(user, [_op(
            "d2", "update", "c2", {"id": task.id, "title": "Z"}, v
        )])
        assert r_upd[0]["status"] == "rejected"
        assert not Task.objects.filter(id=task.id).exists()

    def test_delete_stale_conflicta_no_borra(self):
        """Delete con base_version obsoleta → conflicto, la tarea sobrevive
        con el estado del servidor."""
        user = _user()
        _device(user, "d")
        task = Task.objects.create(owner=user, title="T")
        apply_sync_operations(user, [_op(
            "d", "update", "c1", {"id": task.id, "title": "N"}, task.version
        )])
        task.refresh_from_db()

        r = apply_sync_operations(user, [_op(
            "d", "delete", "c2", {"id": task.id}, 1
        )])
        assert r[0]["status"] == "conflict"
        assert Task.objects.filter(id=task.id).exists()

    def test_sin_base_version_rechazado(self):
        """Update sin base_version → rejected: no hay forma segura de
        detectar conflicto, se prefiere no escribir a ciegas."""
        user = _user()
        _device(user, "d")
        task = Task.objects.create(owner=user, title="T")
        r = apply_sync_operations(user, [_op(
            "d", "update", "c1", {"id": task.id, "title": "X"}
        )])
        assert r[0]["status"] == "rejected"
        task.refresh_from_db()
        assert task.title == "T"

    def test_conflicto_registra_syncoperation(self):
        """El conflicto queda auditado en SyncOperation (conflict_data)."""
        user = _user()
        _device(user, "d")
        task = Task.objects.create(owner=user, title="T")
        apply_sync_operations(user, [_op(
            "d", "update", "c1", {"id": task.id, "title": "N"}, task.version
        )])
        task.refresh_from_db()
        apply_sync_operations(user, [_op(
            "d", "update", "c2", {"id": task.id, "title": "Z"}, 1
        )])
        op = SyncOperation.objects.get(entity_id="c2")
        assert op.status == SyncOperation.Status.CONFLICT
        assert op.conflict_data["title"] == "N"

    def test_version_incrementa_en_cada_update(self):
        """Cada update aplicado incrementa version → bases anteriores
        quedan automáticamente obsoletas."""
        user = _user()
        _device(user, "d")
        task = Task.objects.create(owner=user, title="T")
        for i in range(3):
            apply_sync_operations(user, [_op(
                "d", "update", f"c{i}",
                {"id": task.id, "title": f"v{i}"}, task.version,
            )])
            task.refresh_from_db()
        assert task.version >= 4
        r = apply_sync_operations(user, [_op(
            "d", "update", "stale", {"id": task.id, "title": "old"}, 2
        )])
        assert r[0]["status"] == "conflict"

    def test_update_tarea_ajena_rechazada(self):
        """La operación de otro usuario sobre mi tarea → rejected
        (ownership, no conflict: ni siquiera se revela server_data)."""
        user = _user()
        other = _user("conf_o")
        _device(other, "od")
        task = Task.objects.create(owner=user, title="Mía")
        r = apply_sync_operations(other, [_op(
            "od", "update", "c1", {"id": task.id, "title": "Hack"}, 1
        )])
        assert r[0]["status"] == "rejected"
        assert "server_data" not in r[0]
        task.refresh_from_db()
        assert task.title == "Mía"

    def test_project_update_sin_version_last_write_wins(self):
        """LIMITACIÓN DOCUMENTADA: Project no tiene campo version →
        las updates aplican sin detección de conflicto (blind LWW)."""
        user = _user()
        _device(user, "d")
        from apps.projects.models import Project
        p = Project.objects.create(owner=user, name="P0")
        r = apply_sync_operations(user, [{
            "op_type": "update", "entity_type": "project",
            "entity_id": "p1", "payload": {"id": p.id, "name": "P1"},
            "device_id": "d", "client_timestamp": timezone.now().isoformat(),
        }])
        assert r[0]["status"] == "applied"
        p.refresh_from_db()
        assert p.name == "P1"


@pytest.mark.django_db
class TestFieldLevelMerge:
    """Merge por campo: base_fields permite fusionar cambios no conflictivos."""

    def _op_bf(self, device_id, payload, base_version, base_fields):
        op = _op(device_id, "update", "x", payload, base_version)
        op["base_fields"] = base_fields
        return op

    def test_campos_distintos_mergean(self):
        """Server cambió title, cliente cambia priority → merge, no conflicto."""
        user = _user("merge_u")
        _device(user, "phone")
        task = Task.objects.create(owner=user, title="Original", priority=3)
        v0 = task.version
        # El servidor mueve title (otro campo)
        task.title = "ServerTitle"
        task.save()  # version = v0+1
        # Cliente (base v0) modifica priority: el server no tocó priority
        r = apply_sync_operations(user, [self._op_bf(
            "phone",
            {"id": task.id, "priority": 1},
            v0,
            base_fields={"priority": 3},
        )])
        assert r[0]["status"] == "applied"
        assert r[0]["merged"] is True
        task.refresh_from_db()
        assert task.title == "ServerTitle"  # server se conserva
        assert task.priority == 1           # cliente se aplica

    def test_mismo_campo_conflictua(self):
        """Server cambió title, cliente también cambia title → conflicto."""
        user = _user("conf2_u")
        _device(user, "phone")
        task = Task.objects.create(owner=user, title="Original", priority=3)
        v0 = task.version
        task.title = "ServerTitle"
        task.save()
        r = apply_sync_operations(user, [self._op_bf(
            "phone",
            {"id": task.id, "title": "ClientTitle"},
            v0,
            base_fields={"title": "Original"},
        )])
        assert r[0]["status"] == "conflict"
        task.refresh_from_db()
        assert task.title == "ServerTitle"

    def test_sin_base_fields_comportamiento_objeto(self):
        """Sin base_fields: conflicto a nivel objeto (backward compat)."""
        user = _user("compat_u")
        _device(user, "d")
        task = Task.objects.create(owner=user, title="O", priority=3)
        v0 = task.version
        task.priority = 5
        task.save()
        r = apply_sync_operations(user, [_op(
            "d", "update", "x", {"id": task.id, "title": "C"}, v0
        )])
        assert r[0]["status"] == "conflict"

    def test_completar_offline_mergea_completed_at(self):
        """El merge por campo también aplica efectos de completado."""
        user = _user("comp_u")
        _device(user, "d")
        task = Task.objects.create(owner=user, title="T", priority=3, state="pending")
        v0 = task.version
        task.title = "ServerEdit"
        task.save()
        r = apply_sync_operations(user, [self._op_bf(
            "d",
            {"id": task.id, "state": "completed"},
            v0,
            base_fields={"state": "pending"},
        )])
        assert r[0]["status"] == "applied"
        task.refresh_from_db()
        assert task.state == "completed"
        assert task.completed_at is not None
