"""Tests para: comment threading/reactions, activity feed,
automations programadas, burnup."""
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.tasks.models import Comment, Sprint, Task

User = get_user_model()


@pytest.mark.django_db
class TestCommentThreading:
    def _task(self):
        u = User.objects.get(username="user")
        return Task.objects.create(owner=u, title="t")

    def test_reply_con_parent(self, authed_client):
        c = authed_client
        task = self._task()
        c.post(f"/api/tasks/{task.id}/comments/", {"body": "root"})
        root = Comment.objects.get()
        resp = c.post(f"/api/tasks/{task.id}/comments/", {
            "body": "respuesta", "parent": root.id,
        })
        assert resp.status_code == 201
        reply = Comment.objects.get(body="respuesta")
        assert reply.parent == root
        # replies_count expuesto (listado vía CommentViewSet)
        listing = c.get(f"/api/comments/?task={task.id}")
        data = listing.json()
        items = data if isinstance(data, list) else data.get("results", [])
        root_ser = next(x for x in items if x["id"] == root.id)
        assert root_ser["replies_count"] == 1

    def test_reply_padre_otra_tarea_400(self, authed_client):
        c = authed_client
        t1 = self._task()
        u = User.objects.get(username="user")
        t2 = Task.objects.create(owner=u, title="t2")
        c.post(f"/api/tasks/{t1.id}/comments/", {"body": "root"})
        root = Comment.objects.get()
        resp = c.post(f"/api/tasks/{t2.id}/comments/", {
            "body": "x", "parent": root.id,
        })
        assert resp.status_code == 400

    def test_un_solo_nivel(self, authed_client):
        c = authed_client
        task = self._task()
        c.post(f"/api/tasks/{task.id}/comments/", {"body": "a"})
        a = Comment.objects.get(body="a")
        c.post(f"/api/tasks/{task.id}/comments/", {"body": "b", "parent": a.id})
        b = Comment.objects.get(body="b")
        # respuesta a respuesta → 400 (un nivel max)
        resp = c.post(f"/api/tasks/{task.id}/comments/", {
            "body": "c", "parent": b.id,
        })
        assert resp.status_code == 400


@pytest.mark.django_db
class TestCommentReactions:
    def _comment(self):
        u = User.objects.get(username="user")
        task = Task.objects.create(owner=u, title="t")
        return Comment.objects.create(task=task, author=u, body="x")

    def test_react_añade(self, authed_client):
        c = authed_client
        cm = self._comment()
        resp = c.post(f"/api/comments/{cm.id}/react/", {"emoji": "👍"})
        assert resp.status_code == 200
        uid = User.objects.get(username="user").id
        cm.refresh_from_db()
        assert cm.reactions["👍"] == [uid]

    def test_react_toggle_quita(self, authed_client):
        c = authed_client
        cm = self._comment()
        c.post(f"/api/comments/{cm.id}/react/", {"emoji": "🎉"})
        c.post(f"/api/comments/{cm.id}/react/", {"emoji": "🎉"})
        cm.refresh_from_db()
        assert "🎉" not in cm.reactions

    def test_react_varios_usuarios(self, authed_client):
        """Dos usuarios con acceso al proyecto pueden reaccionar al mismo
        comentario (un user_id por usuario)."""
        c = authed_client
        u = User.objects.get(username="user")
        other, _ = User.objects.get_or_create(
            username="cr_o", defaults={"email": "cr_o@x.com"}
        )
        from apps.collaboration.models import ProjectMember
        from apps.projects.models import Project
        proj = Project.objects.create(owner=u, name="Shared")
        ProjectMember.objects.create(project=proj, user=other, role="viewer")
        task = Task.objects.create(owner=u, project=proj, title="t")
        cm = Comment.objects.create(task=task, author=u, body="x")

        c.post(f"/api/comments/{cm.id}/react/", {"emoji": "👍"})
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken
        c2 = APIClient()
        c2.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(other).access_token}")
        resp = c2.post(f"/api/comments/{cm.id}/react/", {"emoji": "👍"})
        assert resp.status_code == 200
        cm.refresh_from_db()
        assert len(cm.reactions["👍"]) == 2

    def test_react_sin_acceso_404(self, authed_client):
        """Un usuario sin acceso a la tarea no puede reaccionar."""
        cm = self._comment()
        other, _ = User.objects.get_or_create(
            username="cr_o2", defaults={"email": "cr_o2@x.com"}
        )
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken
        c2 = APIClient()
        c2.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(other).access_token}")
        assert c2.post(f"/api/comments/{cm.id}/react/", {"emoji": "👍"}).status_code == 404

    def test_react_sin_emoji_400(self, authed_client):
        c = authed_client
        cm = self._comment()
        assert c.post(f"/api/comments/{cm.id}/react/", {}).status_code == 400


@pytest.mark.django_db
class TestActivityFeed:
    def test_feed_devuelve_actividad_y_audit(self, authed_client):
        c = authed_client
        u = User.objects.get(username="user")
        task = Task.objects.create(owner=u, title="feed t")
        # Un comentario vía API genera TaskActivity (COMMENTED)
        c.post(f"/api/tasks/{task.id}/comments/", {"body": "hola"})
        resp = c.get("/api/activity-feed/")
        assert resp.status_code == 200
        feed = resp.json()
        assert any(e["kind"] == "task_activity" for e in feed)
        assert feed[0]["created_at"] >= feed[-1]["created_at"]  # desc

    def test_feed_no_ve_actividad_ajena(self, authed_client):
        c = authed_client
        other, _ = User.objects.get_or_create(
            username="af_o", defaults={"email": "af_o@x.com"}
        )
        from apps.tasks.models import TaskActivity
        task = Task.objects.create(owner=other, title="ajena")
        TaskActivity.objects.create(
            task=task, actor=other, action="created", new_value="x"
        )
        resp = c.get("/api/activity-feed/")
        assert not any("ajena" in e["summary"] for e in resp.json())

    def test_feed_limit(self, authed_client):
        c = authed_client
        u = User.objects.get(username="user")
        for i in range(5):
            t = Task.objects.create(owner=u, title=f"t{i}")
            t.state = "in_progress"
            t.save()
        resp = c.get("/api/activity-feed/?limit=3")
        assert len(resp.json()) <= 3


@pytest.mark.django_db
class TestScheduledAutomations:
    def test_scheduled_ejecuta_primera_vez(self):
        from apps.automations.engine import run_daily_checks
        from apps.automations.models import AutomationRule
        u, _ = User.objects.get_or_create(
            username="sa_u", defaults={"email": "sa_u@x.com"}
        )
        rule = AutomationRule.objects.create(
            owner=u, name="cada 8h",
            trigger=AutomationRule.Trigger.SCHEDULED,
            action=AutomationRule.Action.CREATE_NOTIFICATION,
            action_params={"title": "check", "message": "m"},
            schedule_hours=8,
        )
        results = run_daily_checks()
        assert any(r["rule"] == "cada 8h" for r in results)
        rule.refresh_from_db()
        assert rule.trigger_count == 1

    def test_scheduled_respeta_intervalo(self):
        from apps.automations.engine import run_daily_checks
        from apps.automations.models import AutomationRule
        u, _ = User.objects.get_or_create(
            username="sa_u2", defaults={"email": "sa_u2@x.com"}
        )
        AutomationRule.objects.create(
            owner=u, name="cada 24h",
            trigger=AutomationRule.Trigger.SCHEDULED,
            action=AutomationRule.Action.CREATE_NOTIFICATION,
            action_params={"title": "x", "message": "x"},
            schedule_hours=24,
            last_triggered_at=timezone.now() - timedelta(hours=2),
        )
        results = run_daily_checks()
        # Aún no toca: no aparece en resultados
        assert not any(r.get("rule") == "cada 24h" for r in results)

    def test_scheduled_ejecuta_si_intervalo_pasado(self):
        from apps.automations.engine import run_daily_checks
        from apps.automations.models import AutomationRule
        u, _ = User.objects.get_or_create(
            username="sa_u3", defaults={"email": "sa_u3@x.com"}
        )
        AutomationRule.objects.create(
            owner=u, name="cada 4h",
            trigger=AutomationRule.Trigger.SCHEDULED,
            action=AutomationRule.Action.CREATE_NOTIFICATION,
            action_params={"title": "x", "message": "x"},
            schedule_hours=4,
            last_triggered_at=timezone.now() - timedelta(hours=5),
        )
        results = run_daily_checks()
        assert any(r["rule"] == "cada 4h" for r in results)


@pytest.mark.django_db
class TestBurnup:
    def _sprint(self, owner):
        p = Sprint.objects.create(
            owner=owner, name="S",
            start_date=timezone.now().date() - timedelta(days=3),
            end_date=timezone.now().date() + timedelta(days=3),
        )
        return p

    def test_burnup_series(self):
        from apps.tasks.advanced_metrics import get_burnup_data
        u, _ = User.objects.get_or_create(
            username="bu_u", defaults={"email": "bu_u@x.com"}
        )
        sprint = self._sprint(u)
        t = Task.objects.create(owner=u, sprint=sprint, title="t",
                                story_points=5, state="completed")
        t.completed_at = timezone.now()
        t.save()
        data = get_burnup_data(u, sprint.id)
        assert data["total_points"] == 5
        last = data["series"][-1]
        assert last["completed"] == 5
        assert last["scope"] == 5

    def test_burnup_endpoint(self, authed_client):
        c = authed_client
        u = User.objects.get(username="user")
        sprint = self._sprint(u)
        resp = c.get(f"/api/tasks/burnup/?sprint_id={sprint.id}")
        assert resp.status_code == 200
        assert "series" in resp.json()

    def test_burnup_404_sin_sprint(self, authed_client):
        c = authed_client
        assert c.get("/api/tasks/burnup/").status_code == 400
        assert c.get("/api/tasks/burnup/?sprint_id=999").status_code == 404
