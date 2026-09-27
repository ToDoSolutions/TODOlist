"""Tests para las aprobaciones de tareas (TaskApproval).

- POST /api/tasks/{id}/request_approval/ (escritura requerida)
- POST /api/tasks/{id}/approve/ y /reject/ (solo el approver del último pending)
- Serializer: approvals, pending_approval_for_me, logged_seconds
"""
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.collaboration.models import ProjectMember
from apps.notifications.models import Notification
from apps.tasks.models import Task, TaskApproval, TimeEntry

User = get_user_model()


@pytest.fixture
def third_user(db):
    return User.objects.create_user(
        email="third@test.com", username="third", password="testpass123"
    )


@pytest.fixture
def third_client(third_user):
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(third_user).access_token}"
    )
    return client


@pytest.fixture
def member_membership(project, other_user):
    """other_user como editor (escritura) del proyecto."""
    return ProjectMember.objects.create(
        project=project, user=other_user, role=ProjectMember.Role.EDITOR
    )


@pytest.fixture
def viewer_membership(project, other_user):
    """other_user como viewer (solo lectura) del proyecto."""
    return ProjectMember.objects.create(
        project=project, user=other_user, role=ProjectMember.Role.VIEWER
    )


@pytest.fixture
def pending_approval(task, user, other_user, member_membership):
    return TaskApproval.objects.create(
        task=task, requester=user, approver=other_user, note="Porfa"
    )


# ------------------------------------------------------------------
# request_approval
# ------------------------------------------------------------------


@pytest.mark.django_db
class TestRequestApproval:
    def test_request_creates_pending_and_notifies(
        self, authed_client, user, other_user, task, member_membership
    ):
        resp = authed_client.post(
            f"/api/tasks/{task.id}/request_approval/",
            {"approver": other_user.id, "note": "Revisa esto"},
            format="json",
        )
        assert resp.status_code == 201, resp.data
        approval = TaskApproval.objects.get(task=task)
        assert approval.status == TaskApproval.Status.PENDING
        assert approval.requester == user
        assert approval.approver == other_user
        assert approval.note == "Revisa esto"
        assert approval.decided_at is None

        assert Notification.objects.filter(
            recipient=other_user, type="approval_request", task=task
        ).exists()

    def test_request_requires_write_access(
        self, authed_client_other, user, task, viewer_membership
    ):
        """Un viewer del proyecto solo tiene lectura: 403 al solicitar."""
        resp = authed_client_other.post(
            f"/api/tasks/{task.id}/request_approval/",
            {"approver": user.id},
            format="json",
        )
        assert resp.status_code == 403
        assert not TaskApproval.objects.filter(task=task).exists()

    def test_request_approver_must_have_project_access(
        self, authed_client, third_user, task
    ):
        """El approver no es miembro del proyecto → 400."""
        resp = authed_client.post(
            f"/api/tasks/{task.id}/request_approval/",
            {"approver": third_user.id},
            format="json",
        )
        assert resp.status_code == 400
        assert not TaskApproval.objects.filter(task=task).exists()

    def test_request_on_projectless_task_allows_any_user(
        self, authed_client, user, other_user
    ):
        """Sin proyecto, cualquier usuario activo puede ser approver."""
        task = Task.objects.create(owner=user, project=None, title="Inbox")
        resp = authed_client.post(
            f"/api/tasks/{task.id}/request_approval/",
            {"approver": other_user.id},
            format="json",
        )
        assert resp.status_code == 201, resp.data

    def test_request_missing_approver_400(self, authed_client, task):
        resp = authed_client.post(
            f"/api/tasks/{task.id}/request_approval/", {}, format="json"
        )
        assert resp.status_code == 400

    def test_request_unknown_approver_400(self, authed_client, task):
        resp = authed_client.post(
            f"/api/tasks/{task.id}/request_approval/",
            {"approver": 999999},
            format="json",
        )
        assert resp.status_code == 400


# ------------------------------------------------------------------
# approve / reject
# ------------------------------------------------------------------


@pytest.mark.django_db
class TestApprovalDecision:
    def test_approve_by_approver(
        self, authed_client_other, user, task, pending_approval
    ):
        resp = authed_client_other.post(
            f"/api/tasks/{task.id}/approve/",
            {"note": "LGTM"},
            format="json",
        )
        assert resp.status_code == 200, resp.data
        pending_approval.refresh_from_db()
        assert pending_approval.status == TaskApproval.Status.APPROVED
        assert pending_approval.decision_note == "LGTM"
        assert pending_approval.decided_at is not None

        # El requester recibe la notificación de decisión
        assert Notification.objects.filter(
            recipient=user, type="approval_decision", task=task
        ).exists()

    def test_reject_by_approver(
        self, authed_client_other, user, task, pending_approval
    ):
        resp = authed_client_other.post(
            f"/api/tasks/{task.id}/reject/",
            {"note": "Falta detalle"},
            format="json",
        )
        assert resp.status_code == 200, resp.data
        pending_approval.refresh_from_db()
        assert pending_approval.status == TaskApproval.Status.REJECTED
        assert pending_approval.decision_note == "Falta detalle"
        assert Notification.objects.filter(
            recipient=user, type="approval_decision", task=task
        ).exists()

    def test_approve_forbidden_for_non_approver(
        self, authed_client, task, pending_approval
    ):
        """El requester (u otro usuario con acceso) no puede decidir."""
        resp = authed_client.post(f"/api/tasks/{task.id}/approve/")
        assert resp.status_code == 403
        pending_approval.refresh_from_db()
        assert pending_approval.status == TaskApproval.Status.PENDING

    def test_reject_forbidden_for_non_approver(
        self, authed_client, task, pending_approval
    ):
        resp = authed_client.post(f"/api/tasks/{task.id}/reject/")
        assert resp.status_code == 403

    def test_approve_without_pending_404(
        self, authed_client, task, member_membership
    ):
        resp = authed_client.post(f"/api/tasks/{task.id}/approve/")
        assert resp.status_code == 404
        resp = authed_client.post(f"/api/tasks/{task.id}/reject/")
        assert resp.status_code == 404

    def test_decision_targets_latest_pending(
        self, authed_client_other, user, other_user, task, pending_approval
    ):
        """Solo el ÚLTIMO pending es decidible."""
        older = pending_approval
        # Una segunda solicitud (más reciente) al mismo approver
        latest = TaskApproval.objects.create(
            task=task, requester=user, approver=other_user
        )
        resp = authed_client_other.post(f"/api/tasks/{task.id}/approve/")
        assert resp.status_code == 200
        latest.refresh_from_db()
        older.refresh_from_db()
        assert latest.status == TaskApproval.Status.APPROVED
        assert older.status == TaskApproval.Status.PENDING

        # Y ahora el viejo es el último pending: también es decidible
        resp = authed_client_other.post(f"/api/tasks/{task.id}/reject/")
        assert resp.status_code == 200
        older.refresh_from_db()
        assert older.status == TaskApproval.Status.REJECTED


# ------------------------------------------------------------------
# Serializer
# ------------------------------------------------------------------


@pytest.mark.django_db
class TestApprovalSerializer:
    def test_approvals_in_task_detail(
        self, authed_client, user, other_user, task, pending_approval
    ):
        resp = authed_client.get(f"/api/tasks/{task.id}/")
        assert resp.status_code == 200
        assert len(resp.data["approvals"]) == 1
        a = resp.data["approvals"][0]
        assert a["id"] == pending_approval.id
        assert a["requester"] == user.id
        assert a["requester_email"] == user.email
        assert a["approver"] == other_user.id
        assert a["approver_email"] == other_user.email
        assert a["status"] == "pending"
        assert a["note"] == "Porfa"
        assert a["decision_note"] == ""
        assert a["decided_at"] is None
        assert resp.data["pending_approval_for_me"] is False

    def test_pending_approval_for_me_flag(
        self, authed_client_other, task, pending_approval
    ):
        resp = authed_client_other.get(f"/api/tasks/{task.id}/")
        assert resp.status_code == 200
        assert resp.data["pending_approval_for_me"] is True

        # Tras decidir ya no hay pending para mí
        authed_client_other.post(f"/api/tasks/{task.id}/approve/")
        resp = authed_client_other.get(f"/api/tasks/{task.id}/")
        assert resp.data["pending_approval_for_me"] is False

    def test_logged_seconds(self, authed_client, user, other_user, task):
        TimeEntry.objects.create(task=task, user=user, duration_seconds=3600)
        TimeEntry.objects.create(
            task=task, user=other_user, duration_seconds=1800
        )
        resp = authed_client.get(f"/api/tasks/{task.id}/")
        assert resp.status_code == 200
        assert resp.data["logged_seconds"] == 5400

    def test_logged_seconds_zero_without_entries(self, authed_client, task):
        resp = authed_client.get(f"/api/tasks/{task.id}/")
        assert resp.status_code == 200
        assert resp.data["logged_seconds"] == 0


# ------------------------------------------------------------------
# Acceso
# ------------------------------------------------------------------


@pytest.mark.django_db
class TestApprovalAccess:
    def test_foreign_task_404(
        self, third_client, third_user, task, pending_approval
    ):
        """Un usuario sin acceso a la tarea no ve ni decide approvals."""
        resp = third_client.post(
            f"/api/tasks/{task.id}/request_approval/",
            {"approver": third_user.id},
            format="json",
        )
        assert resp.status_code == 404
        resp = third_client.post(f"/api/tasks/{task.id}/approve/")
        assert resp.status_code == 404
        resp = third_client.post(f"/api/tasks/{task.id}/reject/")
        assert resp.status_code == 404
