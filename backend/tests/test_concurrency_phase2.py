"""Tests de regresión — Fase 2 de la auditoría (concurrencia/eventos).

Cubre: sprint events solo en transición real (B-01), claim atómico de
send_due_reminders (B-05), Task.version con F() (B-09), sprint close
con lock (B-10), react() atómico (B-11) y snapshot pre_save
consolidado (B-12).
"""
import datetime
from unittest.mock import patch

import pytest

from apps.events.models import OutboxEvent
from apps.notifications.models import Notification
from apps.tasks.models import Comment, Sprint, Task


@pytest.mark.django_db
class TestSprintEventTransitions:
    """B-01: sprint.started/closed solo en la transición real."""

    def _sprint(self, user):
        return Sprint.objects.create(
            owner=user, name="S1",
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 1, 14),
        )

    def test_rename_active_sprint_no_renotifica(self, user):
        s = self._sprint(user)
        s.state = Sprint.SprintState.ACTIVE
        s.save()
        assert Notification.objects.filter(
            type="sprint_started").count() == 1
        assert OutboxEvent.objects.filter(
            event_type="sprint.started").count() == 1
        # Editar un sprint activo NO debe re-notificar ni re-publicar
        s.name = "S1 renamed"
        s.save()
        s.refresh_from_db()
        s.save()
        assert Notification.objects.filter(
            type="sprint_started").count() == 1
        assert OutboxEvent.objects.filter(
            event_type="sprint.started").count() == 1

    def test_close_solo_notifica_en_transicion(self, user):
        s = self._sprint(user)
        s.state = Sprint.SprintState.ACTIVE
        s.save()
        s.state = Sprint.SprintState.CLOSED
        s.save()
        assert Notification.objects.filter(
            type="sprint_closed").count() == 1
        s.name = "renamed closed"
        s.save()
        assert Notification.objects.filter(
            type="sprint_closed").count() == 1
        assert OutboxEvent.objects.filter(
            event_type="sprint.closed").count() == 1

    def test_idempotency_key_estable(self, user):
        """Sin timestamp: el outbox puede deduplicar la transición."""
        s = self._sprint(user)
        s.state = Sprint.SprintState.ACTIVE
        s.save()
        ev = OutboxEvent.objects.get(event_type="sprint.started")
        assert ev.idempotency_key == f"sprint-{s.id}-sprint.started"


@pytest.mark.django_db
class TestDueRemindersClaim:
    """B-05: claim atómico antes de notificar."""

    def test_reminder_marcado_antes_de_notify(self, user, task):
        """Si otro worker reclama primero, notify no corre dos veces."""
        from django.utils import timezone

        from apps.tasks.tasks import send_due_reminders

        task.reminder_at = timezone.now() - datetime.timedelta(minutes=1)
        task.reminder_sent = False
        task.save()

        seen_flags = []

        def spy_notify(**kwargs):
            # El flag ya debe estar reclamado cuando notify corre
            seen_flags.append(
                Task.objects.get(pk=task.pk).reminder_sent)

        with patch(
            "apps.notifications.services.notify", side_effect=spy_notify
        ):
            # el import es lazy dentro de send_due_reminders
            import apps.notifications.services as svc
            orig = svc.notify
            svc.notify = spy_notify
            try:
                result = send_due_reminders()
            finally:
                svc.notify = orig
        assert result["reminders_sent"] == 1
        assert seen_flags == [True]

    def test_segundo_run_no_duplica(self, user, task):
        from django.utils import timezone

        from apps.tasks.tasks import send_due_reminders

        task.reminder_at = timezone.now() - datetime.timedelta(minutes=1)
        task.save()
        send_due_reminders()
        count_after_first = Notification.objects.filter(
            recipient=user, type="reminder").count()
        send_due_reminders()
        assert Notification.objects.filter(
            recipient=user, type="reminder").count() == count_after_first


@pytest.mark.django_db
class TestVersionAtomic:
    """B-09: F("version")+1 → dos saves concurrentes no pierden bump."""

    def test_dos_saves_suman_dos(self, user, task):
        t1 = Task.objects.get(pk=task.pk)
        t2 = Task.objects.get(pk=task.pk)
        t1.title = "a"
        t1.save()
        t2.title = "b"
        t2.save()
        task.refresh_from_db()
        assert task.version == 3  # 1 inicial + 2 saves
        assert isinstance(t2.version, int)

    def test_update_fields_sin_version_no_bumpa(self, user, task):
        task.save(update_fields=["title"])
        task.refresh_from_db()
        assert task.version == 1

    def test_update_fields_con_version_bumpa(self, user, task):
        task.save(update_fields=["title", "version"])
        task.refresh_from_db()
        assert task.version == 2


@pytest.mark.django_db
class TestSprintCloseLock:
    """B-10: close con check dentro del lock."""

    def test_close_dos_veces_segundo_400(self, authed_client, user,
                                       project):
        s = Sprint.objects.create(
            owner=user, name="S", project=project,
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 1, 14),
            state=Sprint.SprintState.ACTIVE,
        )
        r1 = authed_client.post(f"/api/sprints/{s.id}/close/")
        r2 = authed_client.post(f"/api/sprints/{s.id}/close/")
        assert r1.status_code == 200
        assert r2.status_code == 400

    def test_close_mueve_incomplete_con_bump(self, authed_client, user,
                                           project):
        s = Sprint.objects.create(
            owner=user, name="S", project=project,
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 1, 14),
            state=Sprint.SprintState.ACTIVE,
        )
        s2 = Sprint.objects.create(
            owner=user, name="S2", project=project,
            start_date=datetime.date(2026, 2, 1),
            end_date=datetime.date(2026, 2, 14),
        )
        t = Task.objects.create(
            owner=user, title="T", project=project, sprint=s)
        resp = authed_client.post(
            f"/api/sprints/{s.id}/close/",
            {"move_incomplete_to": s2.id}, format="json")
        assert resp.status_code == 200
        t.refresh_from_db()
        assert t.sprint_id == s2.id
        assert t.version == 2  # bump manual en el update masivo


@pytest.mark.django_db
class TestReactAtomic:
    """B-11: react() bajo lock sigue togglando igual."""

    def test_toggle_reaction(self, authed_client, user, task):
        comment = Comment.objects.create(
            task=task, author=user, body="hola")
        r1 = authed_client.post(
            f"/api/comments/{comment.id}/react/", {"emoji": "👍"},
            format="json")
        assert r1.status_code == 200
        comment.refresh_from_db()
        assert comment.reactions == {"👍": [user.id]}
        authed_client.post(
            f"/api/comments/{comment.id}/react/", {"emoji": "👍"},
            format="json")
        comment.refresh_from_db()
        assert comment.reactions == {}


@pytest.mark.django_db
class TestSharedPreSaveSnapshot:
    """B-12: un solo receiver pre_save alimenta los attrs que leen
    notifications/automations (una consulta por save)."""

    def test_attrs_poblados_en_save(self, user, task):
        task.title = "x"
        task.save()
        assert task._old_state == "pending"  # estado previo al save
        assert task._old_state_watch == "pending"
        assert task._old_assignee_id is None

    def test_snapshot_fresco_por_save(self, user, task):
        """Cada save recalcula: el snapshot no se enquista entre saves."""
        task.state = Task.State.IN_PROGRESS
        task.save()
        task.state = Task.State.BLOCKED
        task.save()
        assert task._old_state == Task.State.IN_PROGRESS
