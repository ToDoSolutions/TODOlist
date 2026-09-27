"""Tests de borde para metrics.py: percentiles, branches vacíos, health score."""
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.tasks.metrics import (
    _calculate_health_score,
    _days_between,
    _hours_between,
    _percentile,
    get_backlog_health,
    get_dashboard_summary,
    get_flow_metrics,
    get_pr_metrics,
    get_sprint_metrics,
)
from apps.tasks.models import Sprint, Task, TaskActivity

User = get_user_model()
NOW = timezone.now()


@pytest.fixture
def user(db):
    u, _ = User.objects.get_or_create(
        username="met_e", defaults={"email": "met_e@x.com"}
    )
    return u


class TestPercentile:
    def test_vacio_0(self):
        assert _percentile([], 50) == 0

    def test_un_elemento(self):
        assert _percentile([5], 90) == 5

    def test_mediana_par(self):
        assert _percentile([1, 2, 3, 4], 50) == pytest.approx(2.5)

    def test_p0_es_min(self):
        assert _percentile([3, 1, 2], 0) == 1

    def test_p100_es_max(self):
        assert _percentile([3, 1, 2], 100) == 3

    def test_interpolacion(self):
        # p90 de [1..10] → k = 9*0.9 = 8.1 → 9 + (10-9)*0.1 = 9.1
        assert _percentile(list(range(1, 11)), 90) == pytest.approx(9.1)

    def test_no_ordenado(self):
        assert _percentile([9, 1, 5], 50) == 5


class TestHoursBetween:
    def test_none_start(self):
        assert _hours_between(None, NOW) == 0

    def test_none_end(self):
        assert _hours_between(NOW, None) == 0

    def test_valor(self):
        assert _hours_between(NOW, NOW + timedelta(hours=3)) == 3.0

    def test_dias_between(self):
        assert _days_between(NOW, NOW + timedelta(days=2)) == 2.0


@pytest.mark.django_db
class TestFlowMetrics:
    def test_sin_tareas_ceros(self, user):
        r = get_flow_metrics(user)
        assert r["throughput"] == 0
        assert r["wip"] == 0
        assert r["lead_time"]["mean"] == 0
        assert r["lead_time"]["count"] == 0
        assert r["cycle_time"]["mean"] == 0

    def test_throughput_solo_completadas_en_periodo(self, user):
        Task.objects.create(
            owner=user, title="ok", state="completed",
            completed_at=NOW - timedelta(days=2),
        )
        Task.objects.create(
            owner=user, title="old", state="completed",
            completed_at=NOW - timedelta(days=60),
        )
        Task.objects.create(owner=user, title="pend", state="pending")
        r = get_flow_metrics(user, days=30)
        assert r["throughput"] == 1

    def test_wip_estados(self, user):
        Task.objects.create(owner=user, title="a", state="in_progress")
        Task.objects.create(owner=user, title="b", state="review")
        Task.objects.create(owner=user, title="c", state="blocked")
        Task.objects.create(owner=user, title="d", state="pending")
        r = get_flow_metrics(user)
        assert r["wip"] == 3
        assert r["backlog"] == 1
        assert r["blocked"] == 1

    def test_lead_time_valores(self, user):
        t = Task.objects.create(
            owner=user, title="t", state="completed",
            completed_at=NOW - timedelta(days=1),
        )
        Task.objects.filter(pk=t.pk).update(
            created_at=NOW - timedelta(days=11)
        )
        r = get_flow_metrics(user)
        assert r["lead_time"]["count"] == 1
        assert r["lead_time"]["mean"] == pytest.approx(10.0, abs=0.1)

    def test_cycle_time_requiere_actividad(self, user):
        t = Task.objects.create(
            owner=user, title="t", state="completed",
            completed_at=NOW - timedelta(hours=12),
        )
        # Sin actividad → cycle_time vacío
        r = get_flow_metrics(user)
        assert r["cycle_time"]["count"] == 0
        # Con actividad de in_progress hace 2 días
        act = TaskActivity.objects.create(
            task=t, actor=user, action="state_changed",
            new_value="in_progress",
        )
        TaskActivity.objects.filter(pk=act.pk).update(
            created_at=NOW - timedelta(days=2)
        )
        r = get_flow_metrics(user)
        assert r["cycle_time"]["count"] == 1
        assert r["cycle_time"]["mean"] == pytest.approx(1.5, abs=0.05)

    def test_overdue_cuenta(self, user):
        Task.objects.create(
            owner=user, title="o", state="pending",
            due_date=NOW - timedelta(days=1),
        )
        Task.objects.create(owner=user, title="n", state="pending")
        r = get_flow_metrics(user)
        assert r["overdue"] == 1

    def test_period_days_custom(self, user):
        r = get_flow_metrics(user, days=7)
        assert r["period_days"] == 7


@pytest.mark.django_db
class TestBacklogHealth:
    def test_vacio_score_100(self, user):
        r = get_backlog_health(user)
        assert r["total_open"] == 0
        assert r["health_score"] == 100

    def test_tarea_antigua(self, user):
        t = Task.objects.create(owner=user, title="old", state="pending")
        Task.objects.filter(pk=t.pk).update(
            updated_at=NOW - timedelta(days=40)
        )
        r = get_backlog_health(user)
        assert r["old_tasks_30d"] == 1

    def test_sin_prioridad_p5(self, user):
        Task.objects.create(owner=user, title="p5", priority=5)
        Task.objects.create(owner=user, title="p1", priority=1)
        r = get_backlog_health(user)
        assert r["no_priority"] == 1

    def test_sin_estimacion(self, user):
        Task.objects.create(
            owner=user, title="sinest", story_points=None,
            estimate_hours=None, size="",
        )
        Task.objects.create(owner=user, title="con", story_points=5)
        r = get_backlog_health(user)
        assert r["no_estimate"] == 1

    def test_sin_due_date(self, user):
        Task.objects.create(owner=user, title="sin", due_date=None)
        Task.objects.create(
            owner=user, title="con", due_date=NOW + timedelta(days=5)
        )
        r = get_backlog_health(user)
        assert r["no_due_date"] == 1

    def test_completadas_no_cuentan(self, user):
        Task.objects.create(owner=user, title="c", state="completed")
        r = get_backlog_health(user)
        assert r["total_open"] == 0

    def test_reopened_30d(self, user):
        t = Task.objects.create(owner=user, title="t")
        TaskActivity.objects.create(task=t, actor=user, action="reopened")
        r = get_backlog_health(user)
        assert r["reopened_30d"] == 1


class TestHealthScore:
    def test_total_0_100(self):
        assert _calculate_health_score(0, 0, 0, 0, 0) == 100

    def test_todo_malo_baja(self):
        # 10 tareas, todas viejas + sin est + sin due + vencidas
        s = _calculate_health_score(10, 10, 10, 10, 10)
        # 100 - 30 - 20 - 15 - 35 = 0
        assert s == 0

    def test_parcial(self):
        s = _calculate_health_score(10, 5, 0, 0, 0)
        # 100 - (5/10)*30 = 85
        assert s == 85.0

    def test_no_negativo(self):
        s = _calculate_health_score(1, 1, 1, 1, 1)
        assert s == 0


@pytest.mark.django_db
class TestSprintMetrics:
    def _sprint(self, user, **kw):
        return Sprint.objects.create(
            owner=user, name="S1",
            start_date=NOW.date(), end_date=NOW.date() + timedelta(days=14),
            **kw,
        )

    def test_sprint_inexistente_none(self, user):
        assert get_sprint_metrics(user, 99999) is None

    def test_sprint_vacio(self, user):
        s = self._sprint(user)
        r = get_sprint_metrics(user, s.id)
        assert r["total_tasks"] == 0
        assert r["progress_pct"] == 0
        assert r["scope_creep_pct"] == 0

    def test_progreso(self, user):
        s = self._sprint(user)
        Task.objects.create(owner=user, title="d", sprint=s, state="completed")
        Task.objects.create(owner=user, title="p", sprint=s, state="pending")
        Task.objects.create(owner=user, title="b", sprint=s, state="blocked")
        Task.objects.create(owner=user, title="i", sprint=s, state="in_progress")
        r = get_sprint_metrics(user, s.id)
        assert r["total_tasks"] == 4
        assert r["done"] == 1
        assert r["progress_pct"] == 25.0
        assert r["in_progress"] == 1
        assert r["blocked"] == 1
        assert r["pending"] == 1

    def test_story_points(self, user):
        s = self._sprint(user)
        Task.objects.create(
            owner=user, title="a", sprint=s, state="completed", story_points=5
        )
        Task.objects.create(
            owner=user, title="b", sprint=s, state="pending", story_points=8
        )
        Task.objects.create(owner=user, title="c", sprint=s, story_points=None)
        r = get_sprint_metrics(user, s.id)
        assert r["story_points_total"] == 13
        assert r["story_points_done"] == 5

    def test_scope_creep(self, user):
        s = self._sprint(user)
        # creada hoy (después del start_date de hoy a las 00:00)
        Task.objects.create(owner=user, title="n", sprint=s)
        vieja = Task.objects.create(owner=user, title="v", sprint=s)
        Task.objects.filter(pk=vieja.pk).update(
            created_at=NOW - timedelta(days=10)
        )
        r = get_sprint_metrics(user, s.id)
        assert r["added_after_start"] == 1
        assert r["scope_creep_pct"] == 50.0

    def test_sprint_futuro_sin_scope_creep(self, user):
        """start_date futuro → ninguna tarea cuenta como añadida después."""
        s = Sprint.objects.create(
            owner=user, name="Futuro",
            start_date=NOW.date() + timedelta(days=10),
            end_date=NOW.date() + timedelta(days=20),
        )
        Task.objects.create(owner=user, title="t", sprint=s)
        r = get_sprint_metrics(user, s.id)
        assert r["added_after_start"] == 0
        assert r["scope_creep_pct"] == 0


@pytest.mark.django_db
class TestDashboardSummary:
    def test_vacio(self, user):
        r = get_dashboard_summary(user)
        assert r["open"] == 0
        assert r["active_sprint"] is None
        assert len(r["backlog_trend"]) == 8

    def test_by_state_y_prioridad(self, user):
        Task.objects.create(owner=user, title="a", state="pending", priority=1)
        Task.objects.create(owner=user, title="b", state="blocked", priority=0)
        r = get_dashboard_summary(user)
        assert r["by_state"]["pending"] == 1
        assert r["by_state"]["blocked"] == 1
        assert r["by_priority"]["P1"] == 1
        assert r["by_priority"]["P0"] == 1
        assert r["blocked"] == 1

    def test_active_sprint_incluido(self, user):
        Sprint.objects.create(
            owner=user, name="Activo", state="active",
            start_date=NOW.date(), end_date=NOW.date(),
        )
        r = get_dashboard_summary(user)
        assert r["active_sprint"] is not None
        assert r["active_sprint"]["sprint_name"] == "Activo"

    def test_backlog_trend_formato(self, user):
        Task.objects.create(owner=user, title="t")
        r = get_dashboard_summary(user)
        assert len(r["backlog_trend"]) == 8
        assert all("date" in d and "backlog" in d for d in r["backlog_trend"])


@pytest.mark.django_db
class TestPrMetrics:
    def _repo(self, user):
        from apps.integrations.models import GitHubInstallation, GitHubRepo
        inst = GitHubInstallation.objects.create(
            user=user, installation_id=1, account_login="x"
        )
        return GitHubRepo.objects.create(
            installation=inst, repo_id=1, name="r",
            full_name="o/r", owner="o",
        )

    def test_sin_prs(self, user):
        r = get_pr_metrics(user)
        assert r["total"] == 0
        assert r["merge_time"]["mean"] == 0

    def test_prs_varios_estados(self, user):
        from apps.integrations.models import GitHubPullRequest
        repo = self._repo(user)
        GitHubPullRequest.objects.create(
            repo=repo, pr_number=1, pr_id=1, title="a", state="open",
            created_at_gh=NOW - timedelta(days=10),
        )
        GitHubPullRequest.objects.create(
            repo=repo, pr_number=2, pr_id=2, title="b", state="closed",
            is_merged=True,
            created_at_gh=NOW - timedelta(days=5),
            merged_at=NOW - timedelta(days=1),
        )
        GitHubPullRequest.objects.create(
            repo=repo, pr_number=3, pr_id=3, title="c", state="closed",
            is_merged=False,
            created_at_gh=NOW - timedelta(days=3),
        )
        r = get_pr_metrics(user)
        assert r["total"] == 3
        assert r["open"] == 1
        assert r["merged"] == 1
        assert r["closed_unmerged"] == 1
        assert r["stale_7d"] == 1
        assert r["merge_time"]["count"] == 1
        assert r["merge_time"]["mean"] == pytest.approx(4.0, abs=0.1)

    def test_ci_failed(self, user):
        from apps.integrations.models import GitHubPullRequest
        repo = self._repo(user)
        GitHubPullRequest.objects.create(
            repo=repo, pr_number=1, pr_id=1, title="a", state="open",
            ci_status="failure", created_at_gh=NOW,
        )
        GitHubPullRequest.objects.create(
            repo=repo, pr_number=2, pr_id=2, title="b", state="open",
            ci_status="success", created_at_gh=NOW,
        )
        r = get_pr_metrics(user)
        assert r["ci_failed"] == 1
