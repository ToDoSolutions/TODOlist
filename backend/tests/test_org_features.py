"""Tests de features organizativas: Portfolios, ProjectTemplate y
ProjectStateLabel (labels de display por estado dentro de un proyecto)."""
import pytest

from apps.collaboration.models import ProjectMember
from apps.projects.models import (
    Portfolio,
    Project,
    ProjectStateLabel,
    ProjectTemplate,
)
from apps.tags.models import Tag
from apps.tasks.models import Task


@pytest.mark.django_db
class TestPortfolios:
    def test_portfolio_crud(self, authed_client, user, project):
        resp = authed_client.post("/api/portfolios/", {
            "name": "Work", "color": "#ff0000", "project_ids": [project.id],
        })
        assert resp.status_code == 201
        pid = resp.data["id"]
        assert resp.data["project_ids"] == [project.id]
        pf = Portfolio.objects.get(id=pid, owner=user)
        assert list(pf.projects.values_list("id", flat=True)) == [project.id]

        # update
        resp = authed_client.patch(f"/api/portfolios/{pid}/", {"name": "W2"})
        assert resp.status_code == 200
        pf.refresh_from_db()
        assert pf.name == "W2"

        # list (owner-scoped, paginado)
        resp = authed_client.get("/api/portfolios/")
        assert resp.status_code == 200
        ids = [p["id"] for p in resp.data]
        assert ids == [pid]

        # delete
        assert authed_client.delete(f"/api/portfolios/{pid}/").status_code == 204
        assert not Portfolio.objects.filter(id=pid).exists()

    def test_proyecto_ajeno_rechazado(self, authed_client, user, other_user):
        foreign = Project.objects.create(owner=other_user, name="Ajeno")
        resp = authed_client.post("/api/portfolios/", {
            "name": "Hack", "project_ids": [foreign.id],
        })
        assert resp.status_code == 400
        assert not Portfolio.objects.filter(owner=user).exists()

    def test_proyecto_compartido_aceptado(
        self, authed_client_other, other_user, project
    ):
        # other_user es viewer del project de user → acceso de lectura
        ProjectMember.objects.create(
            project=project, user=other_user, role="viewer")
        resp = authed_client_other.post("/api/portfolios/", {
            "name": "Shared", "project_ids": [project.id],
        })
        assert resp.status_code == 201

    def test_portfolio_ajeno_no_visible(self, authed_client_other, user):
        pf = Portfolio.objects.create(owner=user, name="Privado")
        resp = authed_client_other.get(f"/api/portfolios/{pf.id}/")
        assert resp.status_code == 404
        resp = authed_client_other.get("/api/portfolios/")
        assert resp.data == []


@pytest.mark.django_db
class TestProjectTemplates:
    def test_apply_crea_proyecto_y_tareas(self, authed_client, user):
        tpl = ProjectTemplate.objects.create(
            owner=user, name="Sprint setup",
            config={
                "tasks": [
                    {"title": "Task A", "priority": 1, "task_type": "bug"},
                    {"title": "Task B"},
                ],
                "tags": ["setup", "q1"],
                "state_labels": {"in_progress": "Doing"},
            },
        )
        resp = authed_client.post(
            f"/api/project-templates/{tpl.id}/apply/",
            {"name": "Proyecto Nuevo", "description": "Desc"},
        )
        assert resp.status_code == 201
        assert resp.data["tasks_created"] == 2
        project = Project.objects.get(id=resp.data["project_id"], owner=user)
        assert project.description == "Desc"
        assert project.tasks.count() == 2
        task_a = project.tasks.get(title="Task A")
        assert task_a.priority == 1
        assert task_a.task_type == "bug"
        assert task_a.owner == user
        # tags creados y adjuntados a las tareas
        assert Tag.objects.filter(owner=user, name="setup").exists()
        assert task_a.tags.count() == 2
        # state labels aplicados
        assert ProjectStateLabel.objects.filter(
            project=project, state="in_progress", label="Doing").exists()

    def test_apply_requiere_name(self, authed_client, user):
        tpl = ProjectTemplate.objects.create(owner=user, name="T", config={})
        resp = authed_client.post(
            f"/api/project-templates/{tpl.id}/apply/", {})
        assert resp.status_code == 400
        assert not Project.objects.filter(owner=user).exists()

    def test_builtin_visible_para_otros(
        self, authed_client, authed_client_other, user, other_user
    ):
        tpl = ProjectTemplate.objects.create(
            owner=user, name="Builtin", is_builtin=True, config={})
        resp = authed_client_other.get(f"/api/project-templates/{tpl.id}/")
        assert resp.status_code == 200
        # pero no editable por otro usuario
        resp = authed_client_other.patch(
            f"/api/project-templates/{tpl.id}/", {"name": "Hackeado"})
        assert resp.status_code == 404
        # el owner sí puede aplicarla
        resp = authed_client.post(
            f"/api/project-templates/{tpl.id}/apply/", {"name": "P"})
        assert resp.status_code == 201

    def test_template_ajena_no_listada(
        self, authed_client_other, user
    ):
        ProjectTemplate.objects.create(owner=user, name="Privada", config={})
        resp = authed_client_other.get("/api/project-templates/")
        assert resp.data == []

    def test_from_project_snapshot(self, authed_client, user, project, tag):
        Task.objects.create(
            owner=user, project=project, title="T1", priority=2)
        t2 = Task.objects.create(owner=user, project=project, title="T2")
        t2.tags.add(tag)
        ProjectStateLabel.objects.create(
            project=project, state="blocked", label="Stuck")

        resp = authed_client.post("/api/project-templates/from_project/", {
            "project_id": project.id, "name": "Snapshot",
        })
        assert resp.status_code == 201
        tpl = ProjectTemplate.objects.get(owner=user, name="Snapshot")
        assert len(tpl.config["tasks"]) == 2
        titles = {t["title"] for t in tpl.config["tasks"]}
        assert titles == {"T1", "T2"}
        assert "Trabajo" in tpl.config["tags"]
        assert tpl.config["state_labels"] == {"blocked": "Stuck"}

    def test_from_project_sin_acceso(
        self, authed_client_other, user
    ):
        foreign = Project.objects.create(owner=user, name="Ajeno")
        resp = authed_client_other.post("/api/project-templates/from_project/", {
            "project_id": foreign.id, "name": "Robada",
        })
        assert resp.status_code == 403
        assert not ProjectTemplate.objects.filter(name="Robada").exists()

    def test_from_project_con_acceso_lectura(
        self, authed_client_other, other_user, user
    ):
        project = Project.objects.create(owner=user, name="Compartido")
        ProjectMember.objects.create(
            project=project, user=other_user, role="viewer")
        Task.objects.create(owner=user, project=project, title="X")
        resp = authed_client_other.post("/api/project-templates/from_project/", {
            "project_id": project.id, "name": "Snap viewer",
        })
        assert resp.status_code == 201
        tpl = ProjectTemplate.objects.get(owner=other_user, name="Snap viewer")
        assert len(tpl.config["tasks"]) == 1


@pytest.mark.django_db
class TestStateLabels:
    def test_create_y_upsert_idempotente(self, authed_client, project):
        resp = authed_client.post("/api/state-labels/", {
            "project": project.id, "state": "in_progress", "label": "Doing",
        })
        assert resp.status_code == 201
        # upsert: mismo (project, state) actualiza el label
        resp = authed_client.post("/api/state-labels/", {
            "project": project.id, "state": "in_progress", "label": "WIP",
        })
        assert resp.status_code == 200
        assert ProjectStateLabel.objects.filter(
            project=project, state="in_progress").count() == 1
        assert ProjectStateLabel.objects.get(
            project=project, state="in_progress").label == "WIP"

    def test_estado_invalido_rechazado(self, authed_client, project):
        resp = authed_client.post("/api/state-labels/", {
            "project": project.id, "state": "nonexistent", "label": "X",
        })
        assert resp.status_code == 400
        assert not ProjectStateLabel.objects.filter(project=project).exists()

    def test_sin_acceso_escritura_403(
        self, authed_client_other, other_user, project
    ):
        # viewer: lectura sí, escritura no
        ProjectMember.objects.create(
            project=project, user=other_user, role="viewer")
        resp = authed_client_other.post("/api/state-labels/", {
            "project": project.id, "state": "pending", "label": "X",
        })
        assert resp.status_code == 403
        assert not ProjectStateLabel.objects.filter(project=project).exists()

    def test_proyecto_ajeno_403(self, authed_client_other, project):
        resp = authed_client_other.post("/api/state-labels/", {
            "project": project.id, "state": "pending", "label": "X",
        })
        assert resp.status_code == 403

    def test_list_filtrado_por_proyecto(self, authed_client, user, project):
        ProjectStateLabel.objects.create(
            project=project, state="pending", label="Pend")
        other_p = Project.objects.create(owner=user, name="Otro")
        ProjectStateLabel.objects.create(
            project=other_p, state="blocked", label="Bloq")
        resp = authed_client.get(f"/api/state-labels/?project={project.id}")
        assert resp.status_code == 200
        results = resp.data
        assert len(results) == 1
        assert results[0]["label"] == "Pend"
        assert results[0]["state"] == "pending"

    def test_delete_label(self, authed_client, project):
        sl = ProjectStateLabel.objects.create(
            project=project, state="review", label="QA")
        resp = authed_client.delete(f"/api/state-labels/{sl.id}/")
        assert resp.status_code == 204
        assert not ProjectStateLabel.objects.filter(id=sl.id).exists()
