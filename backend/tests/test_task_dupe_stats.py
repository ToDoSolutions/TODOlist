"""Tests para los endpoints duplicate, snooze_reminder y productivity
de TaskViewSet.

- POST /api/tasks/{id}/duplicate/ — clona la tarea (escalares, tags,
  assignees, checklist y subtareas hijas) con acceso de escritura.
- POST /api/tasks/{id}/snooze_reminder/ — pospone reminder_at N minutos.
- GET  /api/tasks/productivity/?days=N — completadas por día del usuario.
"""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.tasks.models import Comment, Subtask, Task, TaskRelation


def _complete(user, days_ago, **kwargs):
    """Crea una tarea completada hace ``days_ago`` días."""
    return Task.objects.create(
        owner=user,
        state=Task.State.COMPLETED,
        completed_at=timezone.now() - timedelta(days=days_ago),
        **kwargs,
    )


@pytest.mark.django_db
class TestTaskDuplicate:
    def test_duplicate_copies_fields_tags_assignees_subtasks(
        self, authed_client, user, other_user, project, tag
    ):
        task = Task.objects.create(
            owner=user,
            project=project,
            title="Original",
            description="Descripción",
            priority=Task.Priority.P1_VERY_HIGH,
            state=Task.State.IN_PROGRESS,
            task_type=Task.Type.BUG,
            estimate_hours=4,
            story_points=5,
            size="m",
        )
        task.tags.add(tag)
        task.assignees.add(other_user)
        child = Task.objects.create(
            owner=user, project=project, parent=task,
            title="Hija", state=Task.State.IN_PROGRESS,
        )
        grandchild = Task.objects.create(
            owner=user, project=project, parent=child, title="Nieta",
        )

        resp = authed_client.post(f"/api/tasks/{task.id}/duplicate/")
        assert resp.status_code == 201

        clone = Task.objects.get(id=resp.data["id"])
        assert clone.id != task.id
        assert clone.title == "Original"
        assert clone.description == "Descripción"
        assert clone.project_id == project.id
        assert clone.priority == Task.Priority.P1_VERY_HIGH
        assert clone.state == Task.State.IN_PROGRESS
        assert clone.task_type == Task.Type.BUG
        assert clone.estimate_hours == 4
        assert clone.story_points == 5
        assert clone.size == "m"
        assert clone.owner_id == user.id
        assert clone.completed_at is None
        assert clone.reminder_at is None
        assert clone.reminder_sent is False
        assert list(clone.tags.all()) == [tag]
        assert list(clone.assignees.all()) == [other_user]

        children = list(clone.subtasks_children.all())
        assert len(children) == 1
        cloned_child = children[0]
        assert cloned_child.id != child.id
        assert cloned_child.title == "Hija"
        assert cloned_child.state == Task.State.IN_PROGRESS
        assert cloned_child.parent_id == clone.id
        # Solo hijos directos: la nieta sigue colgando de la hija original
        assert cloned_child.subtasks_children.count() == 0
        assert grandchild.parent_id == child.id

    def test_duplicate_resets_completed_to_pending(self, authed_client, user):
        task = Task.objects.create(
            owner=user, title="Hecha",
            state=Task.State.COMPLETED,
            completed_at=timezone.now(),
            reminder_at=timezone.now(),
            reminder_sent=True,
        )
        Task.objects.create(
            owner=user, parent=task, title="Hija hecha",
            state=Task.State.COMPLETED, completed_at=timezone.now(),
        )

        resp = authed_client.post(f"/api/tasks/{task.id}/duplicate/")
        assert resp.status_code == 201

        clone = Task.objects.get(id=resp.data["id"])
        assert clone.state == Task.State.PENDING
        assert clone.completed_at is None
        assert clone.reminder_at is None
        assert clone.reminder_sent is False
        cloned_child = clone.subtasks_children.get()
        assert cloned_child.state == Task.State.PENDING
        assert cloned_child.completed_at is None

    def test_duplicate_skips_comments_relations_watchers(
        self, authed_client, user, other_user
    ):
        task = Task.objects.create(owner=user, title="A")
        other_task = Task.objects.create(owner=user, title="B")
        Comment.objects.create(task=task, author=user, body="hola")
        TaskRelation.objects.create(
            source=task, target=other_task, relation_type="related"
        )
        task.watchers.add(other_user)
        Subtask.objects.create(task=task, title="check", is_done=True, order=1)

        resp = authed_client.post(f"/api/tasks/{task.id}/duplicate/")
        assert resp.status_code == 201

        clone = Task.objects.get(id=resp.data["id"])
        assert clone.comments.count() == 0
        assert clone.outgoing_relations.count() == 0
        assert clone.incoming_relations.count() == 0
        assert clone.watchers.count() == 0
        # La checklist (Subtask) sí forma parte de la copia
        item = clone.subtasks.get()
        assert item.title == "check"
        assert item.is_done is True
        assert item.order == 1

    def test_duplicate_other_user_gets_404(
        self, authed_client_other, user
    ):
        task = Task.objects.create(owner=user, title="Privada")
        resp = authed_client_other.post(f"/api/tasks/{task.id}/duplicate/")
        assert resp.status_code == 404
        assert Task.objects.filter(title="Privada").count() == 1


@pytest.mark.django_db
class TestSnoozeReminder:
    def test_snooze_sets_reminder_and_resets_sent(self, authed_client, task):
        task.reminder_sent = True
        task.save(update_fields=["reminder_sent"])
        before = timezone.now()

        resp = authed_client.post(
            f"/api/tasks/{task.id}/snooze_reminder/",
            {"minutes": 30},
            format="json",
        )
        assert resp.status_code == 200

        task.refresh_from_db()
        assert task.reminder_sent is False
        assert before + timedelta(minutes=30) <= task.reminder_at
        assert task.reminder_at <= timezone.now() + timedelta(minutes=30)
        assert resp.data["reminder_at"] == task.reminder_at.isoformat()

    def test_snooze_default_15_minutes(self, authed_client, task):
        before = timezone.now()
        resp = authed_client.post(f"/api/tasks/{task.id}/snooze_reminder/")
        assert resp.status_code == 200
        task.refresh_from_db()
        assert before + timedelta(minutes=15) <= task.reminder_at
        assert task.reminder_at <= timezone.now() + timedelta(minutes=15)

    @pytest.mark.parametrize("minutes,expected", [(0, 1), (-5, 1), (2000, 1440)])
    def test_snooze_clamps_minutes(self, authed_client, task, minutes, expected):
        before = timezone.now()
        resp = authed_client.post(
            f"/api/tasks/{task.id}/snooze_reminder/",
            {"minutes": minutes},
            format="json",
        )
        assert resp.status_code == 200
        task.refresh_from_db()
        assert before + timedelta(minutes=expected) <= task.reminder_at
        assert task.reminder_at <= timezone.now() + timedelta(minutes=expected)

    def test_snooze_other_user_gets_404(self, authed_client_other, task):
        resp = authed_client_other.post(
            f"/api/tasks/{task.id}/snooze_reminder/",
            {"minutes": 10},
            format="json",
        )
        assert resp.status_code == 404


@pytest.mark.django_db
class TestProductivity:
    def test_daily_counts_zero_fill_and_totals(self, authed_client, user):
        _complete(user, 0)
        _complete(user, 0)
        _complete(user, 2)
        # Fuera de rango (10 días) y no completada: no cuentan
        _complete(user, 10)
        Task.objects.create(owner=user, title="Pendiente")

        resp = authed_client.get("/api/tasks/productivity/?days=7")
        assert resp.status_code == 200

        daily = resp.data["daily"]
        assert len(daily) == 7
        today = timezone.localdate()
        by_date = {d["date"]: d["count"] for d in daily}
        assert by_date[today.isoformat()] == 2
        assert by_date[(today - timedelta(days=1)).isoformat()] == 0
        assert by_date[(today - timedelta(days=2)).isoformat()] == 1
        # Serie continua: un item por día del rango
        assert daily[0]["date"] == (today - timedelta(days=6)).isoformat()
        assert daily[-1]["date"] == today.isoformat()

        assert resp.data["total"] == 3
        assert resp.data["best_day"] == 2
        assert resp.data["avg_per_day"] == round(3 / 7, 1)
        # Hoy tiene ≥1 → racha desde hoy (ayer=0 corta)
        assert resp.data["streak"] == 1

    def test_default_days_is_30(self, authed_client, user):
        resp = authed_client.get("/api/tasks/productivity/")
        assert resp.status_code == 200
        assert len(resp.data["daily"]) == 30

    def test_streak_from_yesterday_when_today_empty(self, authed_client, user):
        _complete(user, 1)
        _complete(user, 2)
        resp = authed_client.get("/api/tasks/productivity/?days=30")
        assert resp.status_code == 200
        assert resp.data["streak"] == 2

    def test_streak_zero_without_recent_completions(self, authed_client, user):
        _complete(user, 5)
        resp = authed_client.get("/api/tasks/productivity/?days=30")
        assert resp.status_code == 200
        assert resp.data["streak"] == 0
        assert resp.data["total"] == 1

    def test_counts_tasks_assigned_to_user(
        self, authed_client, user, other_user
    ):
        # Tarea de otro pero asignada (M2M) al usuario → cuenta
        assigned = _complete(other_user, 0)
        assigned.assignees.add(user)
        # Tarea de otro sin asignar → no cuenta
        _complete(other_user, 0)

        resp = authed_client.get("/api/tasks/productivity/?days=7")
        assert resp.status_code == 200
        assert resp.data["total"] == 1
        assert resp.data["streak"] == 1

    def test_scoped_to_current_user(
        self, authed_client, authed_client_other, user, other_user
    ):
        _complete(other_user, 0)
        _complete(other_user, 1)
        resp = authed_client.get("/api/tasks/productivity/?days=7")
        assert resp.status_code == 200
        assert resp.data["total"] == 0
        assert resp.data["streak"] == 0
        assert all(d["count"] == 0 for d in resp.data["daily"])

        resp_other = authed_client_other.get("/api/tasks/productivity/?days=7")
        assert resp_other.data["total"] == 2
