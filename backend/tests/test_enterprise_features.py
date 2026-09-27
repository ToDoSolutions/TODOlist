"""Tests para: my_work, global search, dependencies, iCal, risks,
meetings, intake forms, dashboards."""
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.projects.models import Project
from apps.tasks.models import Task, TaskRelation

User = get_user_model()


def _me():
    return User.objects.get(username="user")


@pytest.mark.django_db
class TestMyWork:
    def _seed(self):
        u = _me()
        now = timezone.now()
        Task.objects.create(owner=u, assignee=u, title="vencida",
                            due_date=now - timedelta(days=1))
        Task.objects.create(owner=u, assignee=u, title="hoy",
                            due_date=now + timedelta(hours=2))
        Task.objects.create(owner=u, assignee=u, title="prog",
                            state="in_progress")
        Task.objects.create(owner=u, assignee=u, title="futura",
                            due_date=now + timedelta(days=4))
        Task.objects.create(owner=u, title="no mia")  # sin assignee

    def test_my_work_grupos(self, authed_client):
        self._seed()
        resp = authed_client.get("/api/tasks/my-work/")
        assert resp.status_code == 200
        d = resp.json()
        assert [t["title"] for t in d["overdue"]] == ["vencida"]
        assert [t["title"] for t in d["due_today"]] == ["hoy"]
        assert [t["title"] for t in d["in_progress"]] == ["prog"]
        assert [t["title"] for t in d["upcoming"]] == ["futura"]
        assert not any("no mia" in t["title"] for g in d.values()
                       for t in g)

    def test_my_work_blocked(self, authed_client):
        u = _me()
        blocker = Task.objects.create(owner=u, title="bloqueante")
        blocked = Task.objects.create(owner=u, assignee=u, title="bloqueada")
        TaskRelation.objects.create(
            source=blocker, target=blocked,
            relation_type=TaskRelation.RelationType.BLOCKS,
        )
        d = authed_client.get("/api/tasks/my-work/").json()
        assert [t["title"] for t in d["blocked"]] == ["bloqueada"]
        assert d["blocked"][0]["blocked_by"][0]["title"] == "bloqueante"

    def test_my_work_blocked_resuelto_no_aparece(self, authed_client):
        u = _me()
        blocker = Task.objects.create(owner=u, title="done",
                                      state="completed")
        blocked = Task.objects.create(owner=u, assignee=u, title="b")
        TaskRelation.objects.create(
            source=blocker, target=blocked, relation_type="blocks",
        )
        d = authed_client.get("/api/tasks/my-work/").json()
        assert d["blocked"] == []


@pytest.mark.django_db
class TestGlobalSearch:
    def _seed(self):
        u = _me()
        p = Project.objects.create(owner=u, name="api-gateway")
        from apps.tags.models import Tag
        tag = Tag.objects.create(owner=u, name="backend")
        t = Task.objects.create(owner=u, assignee=u, title="problema login oauth",
                                description="fallo 401", project=p,
                                state="in_progress", priority=1)
        t.tags.add(tag)
        Task.objects.create(owner=u, title="otra cosa", state="pending")
        return t

    def test_sintaxis_completa(self, authed_client):
        self._seed()
        d = authed_client.get(
            "/api/tasks/global-search/"
            "?q=assigned:me%20status:open%20tag:backend%20project:api"
        ).json()
        assert len(d["tasks"]) == 1
        assert d["tasks"][0]["title"] == "problema login oauth"

    def test_texto_libre_en_tareas(self, authed_client):
        self._seed()
        d = authed_client.get("/api/tasks/global-search/?q=oauth").json()
        assert [t["title"] for t in d["tasks"]] == ["problema login oauth"]

    def test_frase_literal(self, authed_client):
        self._seed()
        d = authed_client.get(
            '/api/tasks/global-search/?q="problema%20login"'
        ).json()
        assert len(d["tasks"]) == 1

    def test_updated_filter(self, authed_client):
        self._seed()
        d = authed_client.get(
            "/api/tasks/global-search/?q=updated:1d"
        ).json()
        assert len(d["tasks"]) == 2
        d2 = authed_client.get(
            "/api/tasks/global-search/?q=status:closed"
        ).json()
        assert len(d2["tasks"]) == 0

    def test_due_overdue(self, authed_client):
        u = _me()
        Task.objects.create(owner=u, title="vencida",
                            due_date=timezone.now() - timedelta(days=1))
        d = authed_client.get(
            "/api/tasks/global-search/?q=due:overdue"
        ).json()
        assert any(t["title"] == "vencida" for t in d["tasks"])

    def test_busca_comentarios_y_wiki(self, authed_client):
        u = _me()
        task = Task.objects.create(owner=u, title="t")
        from apps.tasks.models import Comment
        Comment.objects.create(task=task, author=u, body="bug critico en prod")
        from apps.wiki.models import WikiPage
        WikiPage.objects.create(owner=u, title="Runbook prod",
                                content="procedimiento de emergencia")
        d = authed_client.get(
            "/api/tasks/global-search/?q=critico"
        ).json()
        assert len(d["comments"]) == 1
        d2 = authed_client.get(
            "/api/tasks/global-search/?q=emergencia"
        ).json()
        assert len(d2["wiki"]) == 1

    def test_sin_q_400(self, authed_client):
        assert authed_client.get("/api/tasks/global-search/").status_code == 400


@pytest.mark.django_db
class TestDependencies:
    def test_dependencies_blocked_y_blocks(self, authed_client):
        u = _me()
        a = Task.objects.create(owner=u, title="A")
        b = Task.objects.create(owner=u, title="B")
        cx = Task.objects.create(owner=u, title="C")
        TaskRelation.objects.create(source=a, target=b, relation_type="blocks")
        TaskRelation.objects.create(source=b, target=cx,
                                    relation_type="depends_on")
        # B está bloqueada por A y bloquea a C
        d = authed_client.get(f"/api/tasks/{b.id}/dependencies/").json()
        assert d["is_blocked"] is True
        assert d["blocked_by"][0]["title"] == "A"
        assert d["blocks"][0]["title"] == "C"

    def test_dependencies_no_blocked_si_source_cerrada(self, authed_client):
        u = _me()
        a = Task.objects.create(owner=u, title="A", state="completed")
        b = Task.objects.create(owner=u, title="B")
        TaskRelation.objects.create(source=a, target=b, relation_type="blocks")
        d = authed_client.get(f"/api/tasks/{b.id}/dependencies/").json()
        assert d["is_blocked"] is False
        assert d["blocked_by"] == []

    def test_dependencies_related(self, authed_client):
        u = _me()
        a = Task.objects.create(owner=u, title="A")
        b = Task.objects.create(owner=u, title="B")
        TaskRelation.objects.create(source=a, target=b,
                                    relation_type="related")
        d = authed_client.get(f"/api/tasks/{b.id}/dependencies/").json()
        assert d["is_blocked"] is False
        assert d["related"][0]["title"] == "A"


@pytest.mark.django_db
class TestICalFeed:
    def test_calendar_ics_formato(self, authed_client):
        u = _me()
        Task.objects.create(owner=u, title="Deadline demo",
                            due_date=timezone.now() + timedelta(days=2))
        resp = authed_client.get("/api/tasks/calendar.ics/")
        assert resp.status_code == 200
        body = resp.content.decode()
        assert "BEGIN:VCALENDAR" in body
        assert "BEGIN:VEVENT" in body
        assert "SUMMARY:Deadline demo" in body
        assert resp["Content-Type"].startswith("text/calendar")

    def test_calendar_escapa_caracteres(self, authed_client):
        u = _me()
        Task.objects.create(owner=u, title="A, con; comas",
                            due_date=timezone.now())
        body = authed_client.get("/api/tasks/calendar.ics/").content.decode()
        assert "A\\, con\\; comas" in body

    def test_calendar_sin_auth_rechazado(self, db):
        from rest_framework.test import APIClient
        resp = APIClient().get("/api/tasks/calendar.ics/")
        assert resp.status_code == 401

    def test_calendar_con_token(self, authed_client):
        from rest_framework.test import APIClient
        resp = authed_client.post("/api/users/me/calendar_token/")
        assert resp.status_code == 200
        token = resp.data["ical_token"]
        # Cliente de calendario sin sesión: solo ?token=
        u = _me()
        Task.objects.create(owner=u, title="Con token",
                            due_date=timezone.now())
        resp = APIClient().get(f"/api/tasks/calendar.ics/?token={token}")
        assert resp.status_code == 200
        assert "Con token" in resp.content.decode()

    def test_calendar_token_invalido(self, db):
        from rest_framework.test import APIClient
        resp = APIClient().get("/api/tasks/calendar.ics/?token=bogus")
        assert resp.status_code == 401

    def test_calendar_token_rotacion_revoca_anterior(self, authed_client):
        from rest_framework.test import APIClient
        anon = APIClient()
        r1 = authed_client.post("/api/users/me/calendar_token/")
        old = r1.data["ical_token"]
        r2 = authed_client.post("/api/users/me/calendar_token/")
        assert r2.data["ical_token"] != old
        # El anterior ya no sirve
        assert anon.get(f"/api/tasks/calendar.ics/?token={old}").status_code == 401
        assert anon.get(f"/api/tasks/calendar.ics/?token={r2.data['ical_token']}").status_code == 200

    def test_calendar_token_revocar(self, authed_client):
        from rest_framework.test import APIClient
        authed_client.post("/api/users/me/calendar_token/")
        resp = authed_client.delete("/api/users/me/calendar_token/")
        assert resp.status_code == 204
        assert APIClient().get("/api/tasks/calendar.ics/?token=x").status_code == 401


@pytest.mark.django_db
class TestProjectRisks:
    def _project(self):
        return Project.objects.create(owner=_me(), name="P")

    def test_crud_risk(self, authed_client):
        c = authed_client
        p = self._project()
        resp = c.post("/api/project-risks/", {
            "project": p.id, "title": "Dependencia proveedor",
            "probability": "high", "impact": "high",
        })
        assert resp.status_code == 201
        assert resp.json()["severity"] == 9

    def test_severity_calculo(self, authed_client):
        from apps.projects.models import ProjectRisk
        p = self._project()
        r = ProjectRisk.objects.create(
            project=p, owner=_me(), title="r",
            probability="medium", impact="low",
        )
        assert r.severity == 2

    def test_viewer_no_crea_risk(self, authed_client):
        p = self._project()
        other, _ = User.objects.get_or_create(
            username="pr_v", defaults={"email": "pr_v@x.com"})
        from apps.collaboration.models import ProjectMember
        ProjectMember.objects.create(project=p, user=other, role="viewer")
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken
        c2 = APIClient()
        c2.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(other).access_token}")
        # viewer puede leer pero no crear
        assert c2.get("/api/project-risks/").status_code == 200
        assert c2.post("/api/project-risks/", {
            "project": p.id, "title": "x",
        }).status_code in (403, 404, 400)


@pytest.mark.django_db
class TestMeetings:
    def test_crear_meeting_y_task_desde_action(self, authed_client):
        c = authed_client
        now = timezone.now()
        resp = c.post("/api/meetings/", {
            "title": "Sprint Retro", "scheduled_at": now.isoformat(),
            "duration_minutes": 45, "decisions": "Mejorar tests",
        })
        assert resp.status_code == 201
        mid = resp.json()["id"]
        resp2 = c.post(f"/api/meetings/{mid}/create_task/",
                       {"title": "Aumentar cobertura"})
        assert resp2.status_code == 201
        detail = c.get(f"/api/meetings/{mid}/").json()
        assert len(detail["tasks_ids"]) == 1

    def test_meeting_aislamiento(self, authed_client):
        c = authed_client
        c.post("/api/meetings/", {
            "title": "Privada", "scheduled_at": timezone.now().isoformat(),
        })
        other, _ = User.objects.get_or_create(
            username="mt_o", defaults={"email": "mt_o@x.com"})
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken
        c2 = APIClient()
        c2.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(other).access_token}")
        assert c2.get("/api/meetings/").json() == []


@pytest.mark.django_db
class TestIntakeForms:
    def _project(self):
        return Project.objects.create(owner=_me(), name="Soporte")

    def _form(self, project):
        c_payload = {
            "project": project.id, "name": "Reportar bug",
            "schema": [
                {"name": "title", "label": "Título", "type": "text",
                 "required": True},
                {"name": "urgencia", "label": "Urgencia", "type": "select",
                 "options": ["baja", "alta"], "required": True},
            ],
            "task_defaults": {"priority": 2, "task_type": "bug",
                              "tags": ["intake"]},
        }
        return c_payload

    def test_submit_crea_tarea(self, authed_client):
        c = authed_client
        p = self._project()
        resp = c.post("/api/intake-forms/", self._form(p), format="json")
        assert resp.status_code == 201
        fid = resp.json()["id"]
        resp2 = c.post(f"/api/intake-forms/{fid}/submit/", {
            "data": {"title": "Login roto", "urgencia": "alta"},
        }, format="json")
        assert resp2.status_code == 201
        task_id = resp2.json()["task_id"]
        task = Task.objects.get(id=task_id)
        assert task.title == "Login roto"
        assert task.priority == 2
        assert task.task_type == "bug"
        assert task.tags.filter(name="intake").exists()
        assert "Urgencia" in task.description

    def test_submit_valida_required(self, authed_client):
        c = authed_client
        p = self._project()
        fid = c.post("/api/intake-forms/", self._form(p), format="json").json()["id"]
        resp = c.post(f"/api/intake-forms/{fid}/submit/", {
            "data": {"urgencia": "baja"},
        }, format="json")
        assert resp.status_code == 400
        assert any("Título" in e for e in resp.json()["errors"])

    def test_submit_valida_opciones(self, authed_client):
        c = authed_client
        p = self._project()
        fid = c.post("/api/intake-forms/", self._form(p), format="json").json()["id"]
        resp = c.post(f"/api/intake-forms/{fid}/submit/", {
            "data": {"title": "x", "urgencia": "critica"},
        }, format="json")
        assert resp.status_code == 400

    def test_schema_invalido_rechazado(self, authed_client):
        c = authed_client
        p = self._project()
        resp = c.post("/api/intake-forms/", {
            "project": p.id, "name": "F", "schema": [],
        }, format="json")
        assert resp.status_code == 400


@pytest.mark.django_db
class TestDashboards:
    def test_crear_y_resolver(self, authed_client):
        c = authed_client
        u = _me()
        Task.objects.create(owner=u, assignee=u, title="t1")
        resp = c.post("/api/dashboards/", {
            "name": "Mi panel",
            "widgets": [
                {"id": "w1", "type": "kpis"},
                {"id": "w2", "type": "my_tasks", "config": {"limit": 5}},
            ],
        }, format="json")
        assert resp.status_code == 201
        did = resp.json()["id"]
        data = c.get(f"/api/dashboards/{did}/data/").json()
        assert len(data["widgets"]) == 2
        kpis = data["widgets"][0]["data"]
        assert kpis["open"] >= 1
        my = data["widgets"][1]["data"]
        assert any(t["title"] == "t1" for t in my["tasks"])

    def test_widget_tipo_desconocido_400(self, authed_client):
        c = authed_client
        resp = c.post("/api/dashboards/", {
            "name": "x", "widgets": [{"type": "noexiste"}],
        }, format="json")
        assert resp.status_code == 400

    def test_widget_types_catalogo(self, authed_client):
        c = authed_client
        d = c.get("/api/dashboards/widget_types/").json()
        assert "kpis" in d and "workload" in d and "blocked" in d
        assert "dora" in d and "audit_dashboard" in d

    def test_widgets_dora_y_audit_dashboard(self, authed_client):
        """Los tipos dora y audit_dashboard resuelven datos reales."""
        c = authed_client
        resp = c.post("/api/dashboards/", {
            "name": "Ops",
            "widgets": [
                {"id": "w1", "type": "dora", "config": {"days": 7}},
                {"id": "w2", "type": "audit_dashboard"},
            ],
        }, format="json")
        assert resp.status_code == 201
        did = resp.json()["id"]
        data = c.get(f"/api/dashboards/{did}/data/").json()
        by_type = {w["type"]: w["data"] for w in data["widgets"]}
        dora = by_type["dora"]
        assert dora["period_days"] == 7
        assert "deployment_frequency_per_week" in dora
        assert "change_failure_rate_pct" in dora
        assert "mttr_hours" in dora
        audit = by_type["audit_dashboard"]
        assert "total_actions" in audit
        assert "by_action" in audit and "by_day" in audit
        assert "by_resource" in audit and "last_30_days" in audit

    def test_solo_un_default(self, authed_client):
        c = authed_client
        d1 = c.post("/api/dashboards/", {
            "name": "A", "widgets": [], "is_default": True,
        }, format="json").json()
        c.post("/api/dashboards/", {
            "name": "B", "widgets": [], "is_default": True,
        }, format="json")
        from apps.dashboards.models import Dashboard
        assert Dashboard.objects.get(id=d1["id"]).is_default is False
