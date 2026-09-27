"""Tests para features enterprise: workload, DORA metrics, wiki."""
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.projects.models import Project
from apps.tasks.advanced_metrics import get_workload_data
from apps.tasks.models import Task
from apps.wiki.models import WikiPage

User = get_user_model()


@pytest.mark.django_db
class TestWorkload:
    def _user(self, name="wl_u"):
        u, _ = User.objects.get_or_create(
            username=name, defaults={"email": f"{name}@x.com"}
        )
        return u

    def test_utilization_por_miembro(self):
        u = self._user()
        Task.objects.create(owner=u, title="t", estimate_hours=20)
        data = get_workload_data(u)
        assert len(data) == 1
        m = data[0]
        assert m["open_tasks"] == 1
        assert m["estimate_hours"] == 20.0
        assert m["utilization"] == 50
        assert m["over_allocated"] is False

    def test_sobreasignacion_detectada(self):
        u = self._user()
        Task.objects.create(owner=u, title="a", estimate_hours=30)
        Task.objects.create(owner=u, title="b", estimate_hours=25)
        m = get_workload_data(u)[0]
        assert m["estimate_hours"] == 55.0
        assert m["utilization"] == 138
        assert m["over_allocated"] is True

    def test_assignee_tambien_suma(self):
        u = self._user()
        other = self._user("wl_o")
        Task.objects.create(owner=u, assignee=other, title="t",
                            estimate_hours=8)
        data = {m["user_id"]: m for m in get_workload_data(u)}
        # La tarea suma tanto al owner como al assignee
        assert data[u.id]["estimate_hours"] == 8.0
        assert data[other.id]["estimate_hours"] == 8.0

    def test_tareas_cerradas_no_cuentan(self):
        u = self._user()
        Task.objects.create(owner=u, title="done", estimate_hours=40,
                            state="completed")
        Task.objects.create(owner=u, title="open", estimate_hours=4)
        m = get_workload_data(u)[0]
        assert m["estimate_hours"] == 4.0
        assert m["open_tasks"] == 1

    def test_due_soon_flag(self):
        u = self._user()
        Task.objects.create(owner=u, title="soon", estimate_hours=1,
                            due_date=timezone.now() + timedelta(days=3))
        Task.objects.create(owner=u, title="far", estimate_hours=1,
                            due_date=timezone.now() + timedelta(days=30))
        m = get_workload_data(u)[0]
        assert m["due_soon"] == 1

    def test_ordenado_por_utilizacion_desc(self):
        u = self._user()
        other = self._user("wl_o2")
        p = Project.objects.create(owner=u, name="P")
        Task.objects.create(owner=u, title="a", project=p, estimate_hours=4)
        Task.objects.create(owner=other, title="b", project=p,
                            estimate_hours=36)
        data = get_workload_data(u)
        assert data[0]["estimate_hours"] == 36.0

    def test_workload_endpoint(self, authed_client):
        c = authed_client
        resp = c.get("/api/tasks/workload/")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


@pytest.mark.django_db
class TestDoraMetrics:
    def _setup(self):
        from apps.integrations.models import (
            GitHubCheckRun,
            GitHubInstallation,
            GitHubPullRequest,
            GitHubRelease,
            GitHubRepo,
        )
        u, _ = User.objects.get_or_create(
            username="dora_u", defaults={"email": "dora_u@x.com"}
        )
        inst = GitHubInstallation.objects.create(
            user=u, installation_id=1, account_login="me"
        )
        repo = GitHubRepo.objects.create(
            installation=inst, repo_id=1, name="r", full_name="me/r"
        )
        return u, repo, GitHubPullRequest, GitHubRelease, GitHubCheckRun

    def test_dora_metrics_calculo(self):
        u, repo, PR, Rel, Check = self._setup()
        from apps.integrations.dora import get_dora_metrics
        now = timezone.now()
        Rel.objects.create(repo=repo, release_id=1, tag_name="v1",
                           state="published", published_at=now,
                           html_url="x")
        PR.objects.create(
            repo=repo, pr_number=1, pr_id=1, title="p",
            is_merged=True, merged_at=now,
            created_at_gh=now - timedelta(hours=10), html_url="x",
        )
        Check.objects.create(repo=repo, check_id=1, name="ci",
                             status="completed", conclusion="failure",
                             started_at=now - timedelta(hours=2))
        Check.objects.create(repo=repo, check_id=2, name="ci",
                             status="completed", conclusion="success",
                             started_at=now - timedelta(hours=1))
        m = get_dora_metrics(u, days=90)
        assert m["deployment_frequency_per_week"] > 0
        assert m["lead_time_for_changes_hours"] == 10.0
        assert m["change_failure_rate_pct"] == 50.0
        assert m["mttr_hours"] == 1.0
        assert m["samples"]["check_runs"] == 2

    def test_dora_sin_datos(self):
        u, _, *_ = self._setup()
        from apps.integrations.dora import get_dora_metrics
        m = get_dora_metrics(u)
        assert m["deployment_frequency_per_week"] == 0.0
        assert m["lead_time_for_changes_hours"] is None
        assert m["change_failure_rate_pct"] == 0.0
        assert m["mttr_hours"] is None

    def test_dora_endpoint(self, authed_client):
        c = authed_client
        resp = c.get("/api/metrics/dora/")
        assert resp.status_code == 200
        assert "deployment_frequency_per_week" in resp.json()

    def test_dora_endpoint_days_param(self, authed_client):
        c = authed_client
        resp = c.get("/api/metrics/dora/?days=30")
        assert resp.json()["period_days"] == 30
        # Clamp: days fuera de rango se ajusta
        resp2 = c.get("/api/metrics/dora/?days=9999")
        assert resp2.json()["period_days"] == 365


@pytest.mark.django_db
class TestWiki:
    def _user(self, name="wiki_u"):
        u, _ = User.objects.get_or_create(
            username=name, defaults={"email": f"{name}@x.com"}
        )
        return u

    def test_crear_pagina(self, authed_client):
        c = authed_client
        resp = c.post("/api/wiki/", {
            "title": "Arquitectura", "content": "# Doc",
        })
        assert resp.status_code == 201
        assert WikiPage.objects.get().title == "Arquitectura"

    def test_jerarquia_padre_hijos(self, authed_client):
        c = authed_client
        p = c.post("/api/wiki/", {"title": "Root"}).json()
        ch = c.post("/api/wiki/", {"title": "Child", "parent": p["id"]}).json()
        detail = c.get(f"/api/wiki/{p['id']}/").json()
        assert detail["children_count"] == 1
        assert ch["parent"] == p["id"]

    def test_no_puede_ser_su_propio_padre(self, authed_client):
        c = authed_client
        p = c.post("/api/wiki/", {"title": "R"}).json()
        resp = c.patch(f"/api/wiki/{p['id']}/", {"parent": p["id"]})
        assert resp.status_code == 400

    def test_padre_mismo_proyecto(self, authed_client):
        c = authed_client
        u = User.objects.get(username="user")
        p1 = Project.objects.create(owner=u, name="P1")
        p2 = Project.objects.create(owner=u, name="P2")
        a = c.post("/api/wiki/", {"title": "A", "project": p1.id}).json()
        resp = c.post("/api/wiki/", {
            "title": "B", "project": p2.id, "parent": a["id"],
        })
        assert resp.status_code == 400

    def test_version_incrementa(self, authed_client):
        c = authed_client
        p = c.post("/api/wiki/", {"title": "V"}).json()
        assert p["version"] == 1
        r = c.patch(f"/api/wiki/{p['id']}/", {"title": "V2"}).json()
        assert r["version"] == 2

    def test_isolation_otro_usuario(self, authed_client):
        c = authed_client
        p = c.post("/api/wiki/", {"title": "Privada"}).json()
        other, _ = User.objects.get_or_create(
            username="wiki_o", defaults={"email": "wiki_o@x.com"}
        )
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken
        c2 = APIClient()
        c2.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(other).access_token}")
        assert c2.get(f"/api/wiki/{p['id']}/").status_code == 404
        assert c2.get("/api/wiki/").json() == []

    def test_viewer_no_edita_pagina_de_proyecto(self, authed_client):
        u = User.objects.get(username="user")
        other = self._user("wiki_v")
        proj = Project.objects.create(owner=u, name="Shared")
        from apps.collaboration.models import ProjectMember
        ProjectMember.objects.create(
            project=proj, user=other, role="viewer"
        )
        page = WikiPage.objects.create(owner=u, project=proj, title="Doc")
        # El viewer puede LEER
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken
        c2 = APIClient()
        c2.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(other).access_token}")
        assert c2.get(f"/api/wiki/{page.id}/").status_code == 200
        # Pero no escribir
        assert c2.patch(f"/api/wiki/{page.id}/", {"title": "X"}).status_code in (403, 404)

    def test_editor_puede_editar(self, authed_client):
        u = User.objects.get(username="user")
        other = self._user("wiki_e")
        proj = Project.objects.create(owner=u, name="Shared")
        from apps.collaboration.models import ProjectMember
        ProjectMember.objects.create(
            project=proj, user=other, role="editor"
        )
        page = WikiPage.objects.create(owner=u, project=proj, title="Doc")
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken
        c2 = APIClient()
        c2.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(other).access_token}")
        resp = c2.patch(f"/api/wiki/{page.id}/", {"title": "Editada"})
        assert resp.status_code == 200
        page.refresh_from_db()
        assert page.title == "Editada"
        assert page.updated_by == other
