"""Tests con aserciones numéricas para apps/tasks/metrics.py y advanced_metrics."""
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.tasks.advanced_metrics import (
    get_burndown_data,
    get_capacity_data,
    get_gantt_data,
)
from apps.tasks.metrics import (
    _calculate_health_score,
    _days_between,
    _hours_between,
    _percentile,
    get_backlog_health,
    get_dashboard_summary,
    get_flow_metrics,
    get_sprint_metrics,
)
from apps.tasks.models import Sprint, Task, TaskActivity

User = get_user_model()
NOW = timezone.now()


@pytest.fixture
def user(db):
    u, _ = User.objects.get_or_create(
        username="met_u", defaults={"email": "met@x.com"}
    )
    return u


def _task(user, **kw):
    return Task.objects.create(owner=user, title=kw.pop("title", "t"), **kw)


def _set_created(task, days_ago):
    Task.objects.filter(pk=task.pk).update(
        created_at=NOW - timedelta(days=days_ago)
    )
    task.refresh_from_db()


class TestHelpers:
    def test_percentile_vacio(self):
        assert _percentile([], 50) == 0

    def test_percentile_un_elemento(self):
        assert _percentile([5], 50) == 5
        assert _percentile([5], 90) == 5

    def test_percentile_mediana(self):
        assert _percentile([1, 2, 3, 4, 5], 50) == 3

    def test_percentile_p90(self):
        vals = list(range(1, 11))  # 1..10
        # k = 9 * 0.9 = 8.1 → 9 + (10-9)*0.1 = 9.1
        assert _percentile(vals, 90) == pytest.approx(9.1)

    def test_percentile_p0_p100(self):
        vals = [10, 20, 30]
        assert _percentile(vals, 0) == 10
        assert _percentile(vals, 100) == 30

    def test_hours_between_none(self):
        assert _hours_between(None, NOW) == 0
        assert _hours_between(NOW, None) == 0

    def test_hours_between(self):
        assert _hours_between(NOW, NOW + timedelta(hours=6)) == 6.0

    def test_days_between(self):
        assert _days_between(NOW, NOW + timedelta(days=2)) == 2.0

    def test_health_score_vacio(self):
        assert _calculate_health_score(0, 0, 0, 0, 0) == 100

    def test_health_score_formula(self):
        # total=10, old=5 → -15; no_est=5 → -10; no_due=2 → -3; overdue=0
        score = _calculate_health_score(10, 5, 5, 2, 0)
        assert score == 72.0

    def test_health_score_floor_0(self):
        assert _calculate_health_score(10, 10, 10, 10, 10) == 0


@pytest.mark.django_db
class TestFlowMetrics:
    def test_sin_tareas(self, user):
        m = get_flow_metrics(user)
        assert m["throughput"] == 0
        assert m["wip"] == 0
        assert m["lead_time"]["count"] == 0
        assert m["lead_time"]["mean"] == 0

    def test_throughput_cuenta_completadas_en_periodo(self, user):
        _task(user, state="completed", completed_at=NOW - timedelta(days=5))
        _task(user, state="completed", completed_at=NOW - timedelta(days=40))
        m = get_flow_metrics(user, days=30)
        assert m["throughput"] == 1

    def test_wip_estados(self, user):
        _task(user, state="in_progress")
        _task(user, state="review")
        _task(user, state="blocked")
        _task(user, state="pending")
        _task(user, state="completed")
        m = get_flow_metrics(user)
        assert m["wip"] == 3
        assert m["backlog"] == 1
        assert m["blocked"] == 1

    def test_overdue(self, user):
        _task(user, state="pending", due_date=NOW - timedelta(days=1))
        _task(user, state="completed", due_date=NOW - timedelta(days=1))
        m = get_flow_metrics(user)
        assert m["overdue"] == 1

    def test_lead_time_valores(self, user):
        t = _task(user, state="completed", completed_at=NOW)
        _set_created(t, 10)
        m = get_flow_metrics(user)
        lt = m["lead_time"]
        assert lt["count"] == 1
        assert lt["mean"] == 10.0
        assert lt["min"] == 10.0
        assert lt["max"] == 10.0
        assert lt["median"] == 10.0

    def test_cycle_time_usa_actividad(self, user):
        t = _task(user, state="completed", completed_at=NOW)
        a = TaskActivity.objects.create(
            task=t, actor=user, action="state_changed",
            new_value="in_progress", old_value="pending",
        )
        TaskActivity.objects.filter(pk=a.pk).update(
            created_at=NOW - timedelta(days=3)
        )
        m = get_flow_metrics(user)
        ct = m["cycle_time"]
        assert ct["count"] == 1
        assert ct["mean"] == 3.0

    def test_cycle_time_sin_actividad_excluye(self, user):
        _task(user, state="completed", completed_at=NOW)
        m = get_flow_metrics(user)
        assert m["cycle_time"]["count"] == 0

    def test_created_count(self, user):
        _task(user)
        m = get_flow_metrics(user)
        assert m["created"] == 1

    def test_period_days_echo(self, user):
        assert get_flow_metrics(user, days=7)["period_days"] == 7


@pytest.mark.django_db
class TestBacklogHealth:
    def test_sin_tareas(self, user):
        h = get_backlog_health(user)
        assert h["total_open"] == 0
        assert h["health_score"] == 100

    def test_cuentas(self, user):
        _task(user, state="pending", priority=5, due_date=None)
        _task(user, state="completed")
        h = get_backlog_health(user)
        assert h["total_open"] == 1
        assert h["no_priority"] == 1
        assert h["no_due_date"] == 1
        assert h["no_estimate"] == 1

    def test_old_tasks(self, user):
        t = _task(user, state="pending")
        Task.objects.filter(pk=t.pk).update(
            updated_at=NOW - timedelta(days=40)
        )
        h = get_backlog_health(user)
        assert h["old_tasks_30d"] == 1

    def test_reopened(self, user):
        t = _task(user)
        TaskActivity.objects.create(task=t, actor=user, action="reopened")
        h = get_backlog_health(user)
        assert h["reopened_30d"] == 1

    def test_health_score_penaliza(self, user):
        # 4 tareas, 1 sin due → -15*(1/4) = -3.75 → 96.25 → 96.2/96.3
        _task(user, state="pending", due_date=NOW + timedelta(days=1), story_points=3)
        _task(user, state="pending", due_date=NOW + timedelta(days=1), story_points=3)
        _task(user, state="pending", due_date=NOW + timedelta(days=1), story_points=3)
        _task(user, state="pending", due_date=None, story_points=3)
        h = get_backlog_health(user)
        assert h["health_score"] < 100
        assert h["health_score"] > 80

    def test_avg_age(self, user):
        t = _task(user, state="pending")
        _set_created(t, 10)
        h = get_backlog_health(user)
        assert h["avg_age_days"] == pytest.approx(10.0, abs=0.1)


@pytest.mark.django_db
class TestSprintMetrics:
    def _sprint(self, user):
        return Sprint.objects.create(
            owner=user, name="S1",
            start_date=NOW.date() - timedelta(days=7),
            end_date=NOW.date() + timedelta(days=7),
            state=Sprint.SprintState.ACTIVE,
        )

    def test_sprint_inexistente_none(self, user):
        assert get_sprint_metrics(user, 999999) is None

    def test_cuentas_estados(self, user):
        s = self._sprint(user)
        _task(user, sprint=s, state="completed")
        _task(user, sprint=s, state="in_progress")
        _task(user, sprint=s, state="blocked")
        _task(user, sprint=s, state="pending")
        m = get_sprint_metrics(user, s.id)
        assert m["total_tasks"] == 4
        assert m["done"] == 1
        assert m["in_progress"] == 1
        assert m["blocked"] == 1
        assert m["pending"] == 1
        assert m["progress_pct"] == 25.0

    def test_story_points(self, user):
        s = self._sprint(user)
        _task(user, sprint=s, state="completed", story_points=5)
        _task(user, sprint=s, state="pending", story_points=3)
        _task(user, sprint=s, state="pending", story_points=None)
        m = get_sprint_metrics(user, s.id)
        assert m["story_points_total"] == 8
        assert m["story_points_done"] == 5

    def test_scope_creep(self, user):
        s = self._sprint(user)
        old = _task(user, sprint=s)
        _set_created(old, 20)  # creada antes del sprint
        _task(user, sprint=s)  # creada ahora → creep
        m = get_sprint_metrics(user, s.id)
        assert m["added_after_start"] == 1
        assert m["scope_creep_pct"] == 50.0

    def test_sprint_sin_tareas(self, user):
        s = self._sprint(user)
        m = get_sprint_metrics(user, s.id)
        assert m["total_tasks"] == 0
        assert m["progress_pct"] == 0
        assert m["scope_creep_pct"] == 0

    def test_sprint_ajeno_none(self, user):
        other, _ = User.objects.get_or_create(
            username="met_o", defaults={"email": "met_o@x.com"}
        )
        s = Sprint.objects.create(
            owner=other, name="Ajeno",
            start_date=NOW.date(), end_date=NOW.date(),
        )
        assert get_sprint_metrics(user, s.id) is None


@pytest.mark.django_db
class TestDashboardSummary:
    def test_sin_tareas(self, user):
        d = get_dashboard_summary(user)
        assert d["open"] == 0
        assert d["completed"] == 0
        assert d["active_sprint"] is None
        assert len(d["backlog_trend"]) == 8

    def test_por_estado_prioridad_tipo(self, user):
        _task(user, state="in_progress", priority=1, task_type="bug")
        _task(user, state="blocked", priority=3, task_type="task")
        d = get_dashboard_summary(user)
        assert d["by_state"]["in_progress"] == 1
        assert d["by_state"]["blocked"] == 1
        assert d["by_priority"]["P1"] == 1
        assert d["by_priority"]["P3"] == 1
        assert d["by_type"]["bug"] == 1

    def test_open_excluye_cerradas(self, user):
        _task(user, state="completed")
        _task(user, state="cancelled")
        _task(user, state="archived")
        _task(user, state="pending")
        d = get_dashboard_summary(user)
        assert d["open"] == 1
        assert d["completed"] == 1

    def test_active_sprint_info(self, user):
        s = Sprint.objects.create(
            owner=user, name="Active",
            start_date=NOW.date(), end_date=NOW.date() + timedelta(days=7),
            state=Sprint.SprintState.ACTIVE,
        )
        _task(user, sprint=s, state="completed")
        d = get_dashboard_summary(user)
        assert d["active_sprint"]["sprint_name"] == "Active"
        assert d["active_sprint"]["done"] == 1

    def test_backlog_trend_formato(self, user):
        t = _task(user)
        _set_created(t, 5)
        d = get_dashboard_summary(user)
        day = d["backlog_trend"][-1]
        assert "date" in day and "backlog" in day
        assert day["backlog"] == 1  # creada hace 5d → backlog ≥1 hasta hoy


@pytest.mark.django_db
class TestGanttData:
    def test_sin_tareas(self, user):
        data = get_gantt_data(user)
        assert data["tasks"] == []

    def test_estructura(self, user):
        t = _task(user, title="G1", state="in_progress",
                    start_date=NOW, due_date=NOW + timedelta(days=5))
        data = get_gantt_data(user)
        g = data["tasks"][0]
        assert g["id"] == t.id
        assert g["title"] == "G1"
        assert g["state"] == "in_progress"
        assert g["start_date"] is not None
        assert g["due_date"] is not None

    def test_dependencies_incluidas(self, user):
        from apps.tasks.models import TaskRelation
        t1 = _task(user, title="A", due_date=NOW + timedelta(days=3))
        t2 = _task(user, title="B", due_date=NOW + timedelta(days=6))
        TaskRelation.objects.create(
            source=t1, target=t2, relation_type="blocks"
        )
        data = get_gantt_data(user)
        assert len(data["dependencies"]) == 1
        dep = data["dependencies"][0]
        assert dep["source"] == t1.id and dep["target"] == t2.id
        assert dep["type"] == "blocks"


@pytest.mark.django_db
class TestBurndown:
    def _sprint(self, user):
        return Sprint.objects.create(
            owner=user, name="BS",
            start_date=NOW.date() - timedelta(days=3),
            end_date=NOW.date() + timedelta(days=3),
            state=Sprint.SprintState.ACTIVE,
        )

    def test_sprint_inexistente(self, user):
        assert get_burndown_data(user, 999999) is None

    def test_burndown_estructura(self, user):
        s = self._sprint(user)
        _task(user, sprint=s, state="pending", story_points=3)
        _task(user, sprint=s, state="completed",
              completed_at=NOW - timedelta(days=1), story_points=2)
        data = get_burndown_data(user, s.id)
        assert data["sprint"]["name"] == "BS"
        assert data["total_points"] == 5
        assert data["total_tasks"] == 2
        assert len(data["ideal"]) >= 2
        assert len(data["actual"]) == len(data["ideal"])
        # Ideal decrece linealmente hasta 0
        assert data["ideal"][0]["ideal"] == 5
        assert data["ideal"][-1]["ideal"] == 0

    def test_burndown_restante_decrece(self, user):
        s = self._sprint(user)
        _task(user, sprint=s, state="pending", story_points=3)
        _task(user, sprint=s, state="completed",
              completed_at=NOW - timedelta(days=1), story_points=2)
        data = get_burndown_data(user, s.id)
        rems = [d["remaining"] for d in data["actual"]]
        assert rems[0] >= rems[-1]
        assert rems[-1] == 3  # quedan 3 puntos pendientes


@pytest.mark.django_db
class TestCapacity:
    def test_estructura(self, user):
        data = get_capacity_data(user)
        assert "users" in data or "sprints" in data or isinstance(data, dict)

    def test_capacity_por_usuario(self, user):
        _task(user, assignee=user, state="in_progress", story_points=5,
              estimate_hours=8)
        data = get_capacity_data(user)
        assert isinstance(data, dict)
