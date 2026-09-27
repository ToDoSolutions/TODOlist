"""Tests de borde para advanced_metrics: gantt, burndown, capacity, roadmap, velocity, audit."""
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.tasks.advanced_metrics import (
    get_audit_dashboard,
    get_burndown_data,
    get_capacity_data,
    get_gantt_data,
    get_roadmap_data,
    get_velocity_data,
)
from apps.tasks.models import Epic, Sprint, Task, TaskRelation, TimeEntry

User = get_user_model()
NOW = timezone.now()


@pytest.fixture
def user(db):
    u, _ = User.objects.get_or_create(
        username="am_e", defaults={"email": "am_e@x.com"}
    )
    return u


def _sprint(user, days=14):
    return Sprint.objects.create(
        owner=user, name="S1",
        start_date=NOW.date(), end_date=NOW.date() + timedelta(days=days),
    )


@pytest.mark.django_db
class TestGanttData:
    def test_vacio(self, user):
        r = get_gantt_data(user)
        assert r["tasks"] == []
        assert r["dependencies"] == []
        assert r["sprints"] == []

    def test_tareas_sin_fecha_ni_sprint_excluidas(self, user):
        Task.objects.create(owner=user, title="sin-fecha")
        r = get_gantt_data(user)
        assert r["tasks"] == []

    def test_con_due_date_incluida(self, user):
        t = Task.objects.create(
            owner=user, title="t", due_date=NOW + timedelta(days=5)
        )
        r = get_gantt_data(user)
        assert len(r["tasks"]) == 1
        assert r["tasks"][0]["id"] == t.id
        assert r["tasks"][0]["due_date"] is not None

    def test_con_sprint_incluida(self, user):
        s = _sprint(user)
        Task.objects.create(owner=user, title="t", sprint=s)
        r = get_gantt_data(user)
        assert len(r["tasks"]) == 1
        assert r["tasks"][0]["sprint"] == "S1"

    def test_proyecto_none_color_default(self, user):
        Task.objects.create(
            owner=user, title="t", due_date=NOW + timedelta(days=1)
        )
        r = get_gantt_data(user)
        assert r["tasks"][0]["project"] is None
        assert r["tasks"][0]["project_color"] == "#1976d2"

    def test_start_date_fallback_created(self, user):
        Task.objects.create(
            owner=user, title="t", due_date=NOW + timedelta(days=1)
        )
        r = get_gantt_data(user)
        assert r["tasks"][0]["start_date"] is not None

    def test_dependencias_incluidas(self, user):
        a = Task.objects.create(
            owner=user, title="a", due_date=NOW + timedelta(days=1)
        )
        b = Task.objects.create(
            owner=user, title="b", due_date=NOW + timedelta(days=2)
        )
        TaskRelation.objects.create(source=a, target=b, relation_type="depends_on")
        r = get_gantt_data(user)
        assert len(r["dependencies"]) == 1
        dep = r["dependencies"][0]
        assert dep["source"] == a.id and dep["target"] == b.id
        assert dep["type"] == "depends_on"

    def test_dependencia_fuera_de_rango_excluida(self, user):
        a = Task.objects.create(
            owner=user, title="a", due_date=NOW + timedelta(days=1)
        )
        b = Task.objects.create(owner=user, title="sin-fecha-ni-sprint")
        TaskRelation.objects.create(source=a, target=b, relation_type="depends_on")
        r = get_gantt_data(user)
        assert r["dependencies"] == []

    def test_sprints_listados(self, user):
        _sprint(user)
        r = get_gantt_data(user)
        assert len(r["sprints"]) == 1
        assert r["sprints"][0]["name"] == "S1"


@pytest.mark.django_db
class TestBurndownData:
    def test_sprint_inexistente_none(self, user):
        assert get_burndown_data(user, 99999) is None

    def test_sprint_vacio(self, user):
        s = _sprint(user)
        r = get_burndown_data(user, s.id)
        assert r["total_points"] == 0
        assert r["total_tasks"] == 0
        assert len(r["ideal"]) == 15
        assert len(r["actual"]) == 15

    def test_ideal_decrece_linealmente(self, user):
        s = _sprint(user, days=4)
        Task.objects.create(
            owner=user, title="t", sprint=s, story_points=8
        )
        r = get_burndown_data(user, s.id)
        ideals = [p["ideal"] for p in r["ideal"]]
        assert ideals[0] == 8
        assert ideals[-1] == 0
        assert ideals == sorted(ideals, reverse=True)

    def test_actual_resta_completados(self, user):
        s = _sprint(user, days=4)
        Task.objects.create(
            owner=user, title="d", sprint=s, state="completed",
            story_points=5, completed_at=NOW,
        )
        Task.objects.create(
            owner=user, title="p", sprint=s, story_points=8
        )
        r = get_burndown_data(user, s.id)
        assert r["total_points"] == 13
        # Hoy completó 5 → actual del último día = 8
        assert r["actual"][-1]["remaining"] == 8

    def test_actual_sprint_un_dia(self, user):
        s = Sprint.objects.create(
            owner=user, name="S0",
            start_date=NOW.date(), end_date=NOW.date(),
        )
        Task.objects.create(owner=user, title="t", sprint=s, story_points=3)
        r = get_burndown_data(user, s.id)
        # days=0 → or 1 → 2 puntos de datos
        assert len(r["ideal"]) == 2

    def test_actual_nunca_negativo(self, user):
        s = _sprint(user, days=2)
        Task.objects.create(
            owner=user, title="d", sprint=s, state="completed",
            story_points=100, completed_at=NOW - timedelta(days=30),
        )
        r = get_burndown_data(user, s.id)
        assert all(p["remaining"] >= 0 for p in r["actual"])


@pytest.mark.django_db
class TestCapacityData:
    def test_vacio(self, user):
        assert get_capacity_data(user)["capacity"] == []

    def test_conteo_por_proyecto(self, user):
        from apps.projects.models import Project
        p = Project.objects.create(owner=user, name="P", color="#fff")
        Task.objects.create(
            owner=user, title="a", project=p, story_points=5,
            state="in_progress",
        )
        Task.objects.create(
            owner=user, title="b", project=p, story_points=3,
            state="blocked",
        )
        Task.objects.create(
            owner=user, title="c", project=p, state="completed",
            story_points=8,
        )
        r = get_capacity_data(user)
        assert len(r["capacity"]) == 1
        cap = r["capacity"][0]
        assert cap["open_tasks"] == 2
        assert cap["total_points"] == 8  # completada no cuenta
        assert cap["in_progress"] == 1
        assert cap["blocked"] == 1
        assert cap["project_color"] == "#fff"

    def test_ordenado_por_puntos_desc(self, user):
        from apps.projects.models import Project
        p1 = Project.objects.create(owner=user, name="P1")
        p2 = Project.objects.create(owner=user, name="P2")
        Task.objects.create(owner=user, title="a", project=p1, story_points=1)
        Task.objects.create(owner=user, title="b", project=p2, story_points=20)
        r = get_capacity_data(user)
        assert r["capacity"][0]["project"] == "P2"


@pytest.mark.django_db
class TestRoadmapData:
    def test_vacio(self, user):
        r = get_roadmap_data(user)
        assert r["epics"] == []
        assert r["milestones"] == []

    def test_epica_con_tareas(self, user):
        e = Epic.objects.create(owner=user, title="E", color="#abc")
        Task.objects.create(
            owner=user, title="d", epic=e, state="completed",
            due_date=NOW + timedelta(days=5),
        )
        Task.objects.create(
            owner=user, title="p", epic=e, state="pending",
            due_date=NOW + timedelta(days=10),
        )
        r = get_roadmap_data(user)
        assert len(r["epics"]) == 1
        lane = r["epics"][0]
        assert lane["total"] == 2
        assert lane["done"] == 1
        assert lane["progress"] == 50.0
        assert lane["end"] == (NOW + timedelta(days=10)).isoformat()

    def test_epica_fechas_explicitas(self, user):
        e = Epic.objects.create(
            owner=user, title="E",
            start_date=NOW.date(), end_date=NOW.date() + timedelta(days=30),
        )
        Task.objects.create(owner=user, title="t", epic=e)
        r = get_roadmap_data(user)
        lane = r["epics"][0]
        assert lane["start"] == NOW.date().isoformat()
        assert lane["end"] == (NOW.date() + timedelta(days=30)).isoformat()

    def test_epica_sin_tareas(self, user):
        Epic.objects.create(owner=user, title="Vacia")
        r = get_roadmap_data(user)
        lane = r["epics"][0]
        assert lane["total"] == 0
        assert lane["progress"] == 0
        assert lane["start"] is None
        assert lane["end"] is None

    def test_cancelled_cuenta_como_done(self, user):
        e = Epic.objects.create(owner=user, title="E")
        Task.objects.create(owner=user, title="c", epic=e, state="cancelled")
        r = get_roadmap_data(user)
        assert r["epics"][0]["done"] == 1

    def test_milestones_sprints(self, user):
        _sprint(user)
        r = get_roadmap_data(user)
        assert len(r["milestones"]) == 1
        assert r["milestones"][0]["name"] == "S1"


@pytest.mark.django_db
class TestVelocityData:
    def test_vacio(self, user):
        r = get_velocity_data(user)
        assert r["velocity"] == []
        assert r["estimated_vs_actual"] == []

    def test_velocity_por_sprint(self, user):
        s = _sprint(user)
        Task.objects.create(
            owner=user, title="d", sprint=s, state="completed",
            story_points=5, estimate_hours=4,
        )
        Task.objects.create(
            owner=user, title="p", sprint=s, story_points=8
        )
        r = get_velocity_data(user)
        assert len(r["velocity"]) == 1
        v = r["velocity"][0]
        assert v["completed_points"] == 5
        assert v["completed_tasks"] == 1

    def test_estimated_vs_actual(self, user):
        s = _sprint(user)
        t = Task.objects.create(
            owner=user, title="d", sprint=s, state="completed",
            estimate_hours=2, completed_at=NOW,
        )
        TimeEntry.objects.create(
            task=t, user=user, duration_seconds=7200,
            started_at=NOW - timedelta(hours=3),
        )
        r = get_velocity_data(user)
        eva = r["estimated_vs_actual"][0]
        assert eva["estimated_hours"] == 2.0
        assert eva["actual_hours"] == 2.0

    def test_sprint_sin_estimaciones_ceros(self, user):
        s = _sprint(user)
        Task.objects.create(owner=user, title="t", sprint=s)
        r = get_velocity_data(user)
        eva = r["estimated_vs_actual"][0]
        assert eva["estimated_hours"] == 0
        assert eva["actual_hours"] == 0


@pytest.mark.django_db
class TestAuditDashboard:
    def test_vacio(self, user):
        r = get_audit_dashboard(user)
        assert r["total_actions"] == 0
        assert r["by_action"] == {}
        assert r["last_30_days"] == 0

    def test_agregacion(self, user):
        from apps.collaboration.models import AuditLog
        AuditLog.objects.create(
            actor=user, action="login", resource_type="user"
        )
        AuditLog.objects.create(
            actor=user, action="login", resource_type="user"
        )
        AuditLog.objects.create(
            actor=user, action="delete", resource_type="task"
        )
        r = get_audit_dashboard(user)
        assert r["total_actions"] == 3
        assert r["by_action"]["login"] == 2
        assert r["by_action"]["delete"] == 1
        assert r["by_resource"]["user"] == 2
        assert r["by_resource"]["task"] == 1
        assert r["last_30_days"] == 3

    def test_solo_propios(self, user):
        from apps.collaboration.models import AuditLog
        other, _ = User.objects.get_or_create(
            username="am_o", defaults={"email": "am_o@x.com"}
        )
        AuditLog.objects.create(actor=other, action="login", resource_type="u")
        AuditLog.objects.create(actor=user, action="login", resource_type="u")
        r = get_audit_dashboard(user)
        assert r["total_actions"] == 1

    def test_antiguo_no_en_30d(self, user):
        from apps.collaboration.models import AuditLog
        log = AuditLog.objects.create(
            actor=user, action="login", resource_type="u"
        )
        AuditLog.objects.filter(pk=log.pk).update(
            created_at=NOW - timedelta(days=60)
        )
        r = get_audit_dashboard(user)
        assert r["total_actions"] == 1
        assert r["last_30_days"] == 0
