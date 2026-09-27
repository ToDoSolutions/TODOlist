"""Tests para las features de colaboración de tareas:

- Recordatorios (reminder_at / reminder_sent + beat send_due_reminders)
- Multi-assignee (Task.assignees)
- Watchers (Task.watchers + endpoints watch/unwatch)
- Cronómetro en vivo (TimeEntry.is_running + timer_*)
"""
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.collaboration.models import ProjectMember
from apps.notifications.models import Notification
from apps.tasks.models import Task, TimeEntry
from apps.tasks.tasks import send_due_reminders

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
def viewer_membership(project, other_user):
    """other_user como viewer (solo lectura) del proyecto."""
    return ProjectMember.objects.create(
        project=project, user=other_user, role=ProjectMember.Role.VIEWER
    )


# ------------------------------------------------------------------
# Recordatorios
# ------------------------------------------------------------------


@pytest.mark.django_db
class TestReminders:
    def test_due_reminder_sends_notification_once(self, user, task):
        task.reminder_at = timezone.now() - timedelta(minutes=1)
        task.save()

        result = send_due_reminders()
        assert result["reminders_sent"] == 1
        assert Notification.objects.filter(
            recipient=user, type="reminder", task=task
        ).count() == 1
        task.refresh_from_db()
        assert task.reminder_sent is True

        # Segunda pasada: no vuelve a notificar
        result = send_due_reminders()
        assert result["reminders_sent"] == 0
        assert Notification.objects.filter(
            recipient=user, type="reminder", task=task
        ).count() == 1

    def test_future_reminder_not_sent(self, user, task):
        task.reminder_at = timezone.now() + timedelta(hours=1)
        task.save()
        result = send_due_reminders()
        assert result["reminders_sent"] == 0
        assert not Notification.objects.filter(type="reminder").exists()

    def test_terminal_states_not_reminded(self, user, task):
        task.reminder_at = timezone.now() - timedelta(minutes=1)
        task.state = Task.State.COMPLETED
        task.save()
        result = send_due_reminders()
        assert result["reminders_sent"] == 0
        task.refresh_from_db()
        assert task.reminder_sent is False

    def test_reminder_fields_in_serializer(self, authed_client, task):
        resp = authed_client.get(f"/api/tasks/{task.id}/")
        assert resp.status_code == 200
        assert "reminder_at" in resp.data
        assert resp.data["reminder_sent"] is False

    def test_changing_reminder_at_resets_sent(self, authed_client, user, task):
        task.reminder_at = timezone.now() - timedelta(minutes=5)
        task.reminder_sent = True
        task.save()
        new_reminder = (timezone.now() + timedelta(hours=2)).isoformat()
        resp = authed_client.patch(
            f"/api/tasks/{task.id}/",
            {"reminder_at": new_reminder},
            format="json",
        )
        assert resp.status_code == 200, resp.data
        task.refresh_from_db()
        assert task.reminder_sent is False


# ------------------------------------------------------------------
# Multi-assignee
# ------------------------------------------------------------------


@pytest.mark.django_db
class TestMultiAssignee:
    def test_set_assignees_via_patch(self, authed_client, other_user, task):
        resp = authed_client.patch(
            f"/api/tasks/{task.id}/",
            {"assignees": [other_user.id]},
            format="json",
        )
        assert resp.status_code == 200, resp.data
        assert task.assignees.filter(id=other_user.id).exists()
        detail = {u["id"]: u for u in resp.data["assignees_detail"]}
        assert detail[other_user.id]["email"] == other_user.email
        assert detail[other_user.id]["username"] == other_user.username

    def test_assignee_sees_and_edits_task(
        self, authed_client, authed_client_other, other_user, task
    ):
        resp = authed_client.patch(
            f"/api/tasks/{task.id}/",
            {"assignees": [other_user.id]},
            format="json",
        )
        assert resp.status_code == 200, resp.data

        # La ve en el listado
        resp = authed_client_other.get("/api/tasks/")
        assert resp.status_code == 200
        ids = [t["id"] for t in resp.data]
        assert task.id in ids

        # GET detalle
        resp = authed_client_other.get(f"/api/tasks/{task.id}/")
        assert resp.status_code == 200

        # Puede editarla (for_user write incluye assignees)
        resp = authed_client_other.patch(
            f"/api/tasks/{task.id}/",
            {"title": "Editada por asignado"},
            format="json",
        )
        assert resp.status_code == 200, resp.data
        task.refresh_from_db()
        assert task.title == "Editada por asignado"

    def test_non_member_gets_404(self, third_client, task):
        resp = third_client.get(f"/api/tasks/{task.id}/")
        assert resp.status_code == 404
        resp = third_client.patch(
            f"/api/tasks/{task.id}/", {"title": "x"}, format="json"
        )
        assert resp.status_code in (403, 404)

    def test_assignee_gets_assignment_notification(
        self, authed_client, user, other_user, task
    ):
        authed_client.patch(
            f"/api/tasks/{task.id}/",
            {"assignees": [other_user.id]},
            format="json",
        )
        assert Notification.objects.filter(
            recipient=other_user, type="task_assigned", task=task
        ).exists()
        # El owner nunca se auto-notifica
        assert not Notification.objects.filter(
            recipient=user, type="task_assigned"
        ).exists()

    def test_assignees_must_exist(self, authed_client, task):
        resp = authed_client.patch(
            f"/api/tasks/{task.id}/",
            {"assignees": [999999]},
            format="json",
        )
        assert resp.status_code == 400


# ------------------------------------------------------------------
# Watchers
# ------------------------------------------------------------------


@pytest.mark.django_db
class TestWatchers:
    def test_watch_and_unwatch_idempotent(
        self, authed_client_other, other_user, task, viewer_membership
    ):
        resp = authed_client_other.post(f"/api/tasks/{task.id}/watch/")
        assert resp.status_code == 200
        assert resp.data["watching"] is True
        # Segundo watch: sigue habiendo un solo watcher
        resp = authed_client_other.post(f"/api/tasks/{task.id}/watch/")
        assert resp.status_code == 200
        assert task.watchers.filter(id=other_user.id).count() == 1

        resp = authed_client_other.delete(f"/api/tasks/{task.id}/unwatch/")
        assert resp.status_code == 200
        assert resp.data["watching"] is False
        assert not task.watchers.filter(id=other_user.id).exists()
        # unwatch de nuevo: idempotente, sin error
        resp = authed_client_other.delete(f"/api/tasks/{task.id}/unwatch/")
        assert resp.status_code == 200

    def test_watcher_can_read_not_write(
        self, authed_client_other, other_user, task
    ):
        task.watchers.add(other_user)
        # GET detalle ok (watchers tienen acceso de lectura)
        resp = authed_client_other.get(f"/api/tasks/{task.id}/")
        assert resp.status_code == 200
        assert resp.data["is_watching"] is True
        assert other_user.id in resp.data["watchers"]
        # PATCH → prohibido (solo lectura)
        resp = authed_client_other.patch(
            f"/api/tasks/{task.id}/", {"title": "hack"}, format="json"
        )
        assert resp.status_code in (403, 404)
        task.refresh_from_db()
        assert task.title != "hack"

    def test_watch_requires_read_access(self, third_client, task):
        """Un usuario sin acceso a la tarea no puede watchearla."""
        resp = third_client.post(f"/api/tasks/{task.id}/watch/")
        assert resp.status_code in (403, 404)
        assert not task.watchers.exists()

    def test_comment_notifies_watcher(
        self, authed_client, user, other_user, task
    ):
        task.watchers.add(other_user)
        resp = authed_client.post(
            f"/api/tasks/{task.id}/comments/",
            {"body": "Comentario para watchers"},
            format="json",
        )
        assert resp.status_code == 201, resp.data
        assert Notification.objects.filter(
            recipient=other_user, type="task_commented", task=task
        ).exists()

    def test_comment_by_author_watcher_not_duplicated(
        self, authed_client, user, other_user, task
    ):
        """El owner ya recibe task_commented; como watcher no debe duplicar."""
        task.watchers.add(user)
        task.watchers.add(other_user)
        authed_client.post(
            f"/api/tasks/{task.id}/comments/",
            {"body": "hola"},
            format="json",
        )
        # owner: una sola notificación (la de notify_on_comment), no dos
        assert (
            Notification.objects.filter(
                recipient=user, type="task_commented", task=task
            ).count()
            <= 1
        )

    def test_state_change_notifies_watcher(
        self, authed_client, other_user, task
    ):
        task.watchers.add(other_user)
        resp = authed_client.patch(
            f"/api/tasks/{task.id}/",
            {"state": "in_progress"},
            format="json",
        )
        assert resp.status_code == 200, resp.data
        assert Notification.objects.filter(
            recipient=other_user, type="task_state_changed", task=task
        ).exists()


# ------------------------------------------------------------------
# Cronómetro en vivo
# ------------------------------------------------------------------


@pytest.mark.django_db
class TestLiveTimer:
    def test_timer_start_creates_running_entry(self, authed_client, user, task):
        resp = authed_client.post(f"/api/tasks/{task.id}/timer_start/")
        assert resp.status_code == 201, resp.data
        assert resp.data["is_running"] is True
        assert resp.data["started_at"] is not None
        entry = TimeEntry.objects.get(task=task, user=user)
        assert entry.is_running is True

    def test_second_start_autostops_previous(
        self, authed_client, user, task, project
    ):
        task2 = Task.objects.create(owner=user, project=project, title="Otra")
        authed_client.post(f"/api/tasks/{task.id}/timer_start/")
        resp = authed_client.post(f"/api/tasks/{task2.id}/timer_start/")
        assert resp.status_code == 201

        # La entrada anterior quedó detenida con duración > 0
        old = TimeEntry.objects.get(task=task, user=user)
        assert old.is_running is False
        assert old.ended_at is not None
        assert old.duration_seconds > 0

        # Solo una running por usuario
        assert (
            TimeEntry.objects.filter(user=user, is_running=True).count() == 1
        )

    def test_timer_stop_computes_duration(self, authed_client, user, task):
        authed_client.post(f"/api/tasks/{task.id}/timer_start/")
        entry = TimeEntry.objects.get(task=task, user=user)
        # Simular que empezó hace una hora
        entry.started_at = timezone.now() - timedelta(hours=1)
        entry.save(update_fields=["started_at"])

        resp = authed_client.post(f"/api/tasks/{task.id}/timer_stop/")
        assert resp.status_code == 200, resp.data
        entry.refresh_from_db()
        assert entry.is_running is False
        assert entry.ended_at is not None
        assert entry.duration_seconds >= 3599

    def test_timer_stop_without_running_404(self, authed_client, task):
        resp = authed_client.post(f"/api/tasks/{task.id}/timer_stop/")
        assert resp.status_code == 404

    def test_timer_status(self, authed_client, task):
        resp = authed_client.get(f"/api/tasks/{task.id}/timer_status/")
        assert resp.status_code == 200
        assert resp.data["running"] is False
        assert resp.data["started_at"] is None

        authed_client.post(f"/api/tasks/{task.id}/timer_start/")
        resp = authed_client.get(f"/api/tasks/{task.id}/timer_status/")
        assert resp.status_code == 200
        assert resp.data["running"] is True
        assert resp.data["started_at"] is not None

    def test_timer_requires_write_access(
        self, authed_client_other, other_user, task
    ):
        """Un watcher (solo lectura) no puede iniciar el cronómetro."""
        task.watchers.add(other_user)
        resp = authed_client_other.post(f"/api/tasks/{task.id}/timer_start/")
        assert resp.status_code in (403, 404)

    def test_time_entry_serializer_exposes_is_running(
        self, authed_client, user, task
    ):
        TimeEntry.objects.create(
            task=task, user=user, duration_seconds=60, is_running=False
        )
        resp = authed_client.get("/api/time-entries/")
        assert resp.status_code == 200
        assert "is_running" in resp.data[0]
