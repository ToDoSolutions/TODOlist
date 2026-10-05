"""Tests de regresión — Fase 3 de la auditoría (paridad de canales).

Cubre: WorkflowTransition en offline sync y CalDAV (B-04), y
pull_changes con tombstones/since naive/proyectos compartidos (B-14).
"""
import base64
import datetime

import pytest
from django.utils import timezone

from apps.collaboration.models import ProjectMember
from apps.offline_sync.services import apply_sync_operations, get_changes_since
from apps.projects.models import Project, WorkflowTransition
from apps.tasks.models import Task


def _op(entity_id, payload, base_version, extra=None):
    op = {
        "op_type": "update",
        "entity_type": "task",
        "entity_id": entity_id,
        "payload": payload,
        "base_version": base_version,
        "client_timestamp": timezone.now(),
        "device_id": "dev1",
    }
    op.update(extra or {})
    return op


@pytest.mark.django_db
class TestSyncWorkflowTransitions:
    """B-04: el push de offline sync respeta el workflow del proyecto."""

    @pytest.fixture(autouse=True)
    def _device(self, user):
        from apps.offline_sync.models import SyncDevice
        SyncDevice.objects.create(
            user=user, device_id="dev1", is_active=True)

    def _restrict_workflow(self, project):
        WorkflowTransition.objects.create(
            project=project, from_state="pending", to_state="in_progress")

    def test_transicion_ilegal_rechazada(self, user, project, task):
        self._restrict_workflow(project)
        results = apply_sync_operations(user, [_op(
            "e1", {"id": task.id, "state": "completed"},
            base_version=task.version)])
        assert results[0]["status"] == "rejected"
        task.refresh_from_db()
        assert task.state == Task.State.PENDING

    def test_transicion_legal_aplicada(self, user, project, task):
        self._restrict_workflow(project)
        results = apply_sync_operations(user, [_op(
            "e2", {"id": task.id, "state": "in_progress"},
            base_version=task.version)])
        assert results[0]["status"] == "applied"
        task.refresh_from_db()
        assert task.state == Task.State.IN_PROGRESS

    def test_estado_invalido_rechazado(self, user, task):
        results = apply_sync_operations(user, [_op(
            "e3", {"id": task.id, "state": "nonsense"},
            base_version=task.version)])
        assert results[0]["status"] == "rejected"

    def test_merge_path_tambien_valida(self, user, project, task):
        """El merge por campo (base_fields) no puede saltarse el
        workflow tampoco."""
        self._restrict_workflow(project)
        # Forzar conflicto por versión: el servidor toca otro campo
        task.title = "otro"
        task.save()
        results = apply_sync_operations(user, [_op(
            "e4", {"id": task.id, "state": "completed"},
            base_version=1,
            extra={"base_fields": {"state": "pending"}})])
        assert results[0]["status"] == "rejected"
        task.refresh_from_db()
        assert task.state == Task.State.PENDING

    def test_create_con_estado_invalido_rechazado(self, user):
        results = apply_sync_operations(user, [{
            "op_type": "create",
            "entity_type": "task",
            "entity_id": "e5",
            "payload": {"title": "T", "state": "nonsense"},
            "client_timestamp": timezone.now(),
            "device_id": "dev1",
        }])
        assert results[0]["status"] == "rejected"


def _basic_auth(token):
    cred = base64.b64encode(f"x:{token}".encode()).decode()
    return {"HTTP_AUTHORIZATION": f"Basic {cred}"}


@pytest.mark.django_db
class TestCalDavWorkflowTransitions:
    """B-04: el PUT CalDAV respeta el workflow del proyecto."""

    def _ics(self, uid, status="COMPLETED"):
        return (
            "BEGIN:VCALENDAR\r\nBEGIN:VTODO\r\n"
            f"UID:{uid}\r\nSUMMARY:T\r\nSTATUS:{status}\r\n"
            "END:VTODO\r\nEND:VCALENDAR\r\n"
        )

    def test_put_transicion_ilegal_403(self, user, project, task, client):
        user.ical_token = "tok123"
        user.save(update_fields=["ical_token"])
        WorkflowTransition.objects.create(
            project=project, from_state="pending", to_state="in_progress")
        resp = client.generic(
            "PUT",
            f"/api/caldav/tasks/task-{task.id}@todolist.ics",
            data=self._ics(f"task-{task.id}@todolist").encode(),
            content_type="text/calendar",
            **_basic_auth("tok123"),
        )
        assert resp.status_code == 403
        task.refresh_from_db()
        assert task.state == Task.State.PENDING

    def test_put_transicion_legal_204(self, user, project, task, client):
        user.ical_token = "tok123"
        user.save(update_fields=["ical_token"])
        WorkflowTransition.objects.create(
            project=project, from_state="pending", to_state="in_progress")
        resp = client.generic(
            "PUT",
            f"/api/caldav/tasks/task-{task.id}@todolist.ics",
            data=self._ics(
                f"task-{task.id}@todolist", status="IN-PROCESS").encode(),
            content_type="text/calendar",
            **_basic_auth("tok123"),
        )
        assert resp.status_code == 204
        task.refresh_from_db()
        assert task.state == Task.State.IN_PROGRESS


@pytest.mark.django_db
class TestPullChanges:
    """B-14: tombstones, since naive y proyectos compartidos."""

    def test_tarea_borrada_devuelve_tombstone(self, user, task):
        task_id = task.id
        task.delete()
        changes = get_changes_since(
            user, timezone.now() - datetime.timedelta(hours=1))
        assert task_id in changes["deleted_task_ids"]
        assert all(t["id"] != task_id for t in changes["tasks"])
        assert changes["truncated"] is False

    def test_since_naive_no_revienta(self, user, task):
        """ISO sin offset → se interpreta como UTC en vez de explotar."""
        naive = timezone.now().replace(tzinfo=None) \
            - datetime.timedelta(hours=1)
        changes = get_changes_since(user, naive)
        assert isinstance(changes["tasks"], list)

    def test_proyecto_compartido_llega_al_pull(self, user, other_user):
        """Un proyecto donde soy miembro (no owner) debe figurar."""
        shared = Project.objects.create(owner=other_user, name="Shared")
        ProjectMember.objects.create(
            project=shared, user=user, role="editor")
        changes = get_changes_since(
            user, timezone.now() - datetime.timedelta(hours=1))
        ids = [p["id"] for p in changes["projects"]]
        assert shared.id in ids

    def test_proyecto_ajeno_no_llega(self, user, other_user):
        private = Project.objects.create(owner=other_user, name="Priv")
        changes = get_changes_since(
            user, timezone.now() - datetime.timedelta(hours=1))
        ids = [p["id"] for p in changes["projects"]]
        assert private.id not in ids
