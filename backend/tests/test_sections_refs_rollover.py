"""Tests de secciones de proyecto (Todoist/Asana), refs legibles
(Linear/Jira) y rollover de sprint al cerrar (Jira)."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.collaboration.models import ProjectMember
from apps.projects.models import Project, ProjectSection
from apps.tasks.models import Sprint, Task

User = get_user_model()


@pytest.fixture
def section(user, project):
    return ProjectSection.objects.create(project=project, name="Por hacer")


@pytest.fixture
def active_sprint(user, project):
    return Sprint.objects.create(
        owner=user,
        project=project,
        name="Sprint 1",
        state=Sprint.SprintState.ACTIVE,
        start_date=timezone.now().date() - timedelta(days=7),
        end_date=timezone.now().date() + timedelta(days=7),
    )


@pytest.fixture
def next_sprint(user, project):
    return Sprint.objects.create(
        owner=user,
        project=project,
        name="Sprint 2",
        state=Sprint.SprintState.PLANNED,
        start_date=timezone.now().date() + timedelta(days=7),
        end_date=timezone.now().date() + timedelta(days=21),
    )


# --- Secciones de proyecto ---


@pytest.mark.django_db
class TestProjectSections:
    def test_create_section(self, authed_client, project):
        resp = authed_client.post("/api/project-sections/", {
            "project": project.id,
            "name": "En progreso",
        }, format="json")
        assert resp.status_code == 201
        assert resp.data["name"] == "En progreso"
        assert resp.data["order"] == 0
        assert ProjectSection.objects.filter(
            project=project, name="En progreso"
        ).exists()

    def test_list_requires_project_param(self, authed_client, section):
        resp = authed_client.get("/api/project-sections/")
        assert resp.status_code == 400
        resp = authed_client.get(
            f"/api/project-sections/?project={section.project_id}"
        )
        assert resp.status_code == 200
        data = (
            resp.data["results"] if isinstance(resp.data, dict)
            else resp.data
        )
        assert len(data) == 1
        assert data[0]["name"] == "Por hacer"

    def test_viewer_can_read_but_not_create(
        self, authed_client_other, other_user, project, section
    ):
        ProjectMember.objects.create(
            project=project, user=other_user, role="viewer"
        )
        resp = authed_client_other.get(
            f"/api/project-sections/?project={project.id}"
        )
        assert resp.status_code == 200
        resp = authed_client_other.post("/api/project-sections/", {
            "project": project.id,
            "name": "No permitido",
        }, format="json")
        assert resp.status_code in (403, 404)
        assert not ProjectSection.objects.filter(name="No permitido").exists()

    def test_outsider_cannot_see_or_write(
        self, authed_client_other, other_user, project, section
    ):
        resp = authed_client_other.get(
            f"/api/project-sections/?project={project.id}"
        )
        assert resp.status_code == 200
        data = (
            resp.data["results"] if isinstance(resp.data, dict)
            else resp.data
        )
        assert data == []
        resp = authed_client_other.post("/api/project-sections/", {
            "project": project.id,
            "name": "Intruso",
        }, format="json")
        assert resp.status_code in (403, 404)
        resp = authed_client_other.get(f"/api/project-sections/{section.id}/")
        assert resp.status_code == 404

    def test_editor_can_create(
        self, authed_client_other, other_user, project
    ):
        ProjectMember.objects.create(
            project=project, user=other_user, role="editor"
        )
        resp = authed_client_other.post("/api/project-sections/", {
            "project": project.id,
            "name": "Review",
        }, format="json")
        assert resp.status_code == 201

    def test_patch_order_and_name(self, authed_client, section):
        resp = authed_client.patch(
            f"/api/project-sections/{section.id}/",
            {"order": 7, "name": "Hecho"},
            format="json",
        )
        assert resp.status_code == 200
        section.refresh_from_db()
        assert section.order == 7
        assert section.name == "Hecho"

    def test_viewer_cannot_patch(
        self, authed_client_other, other_user, project, section
    ):
        ProjectMember.objects.create(
            project=project, user=other_user, role="viewer"
        )
        resp = authed_client_other.patch(
            f"/api/project-sections/{section.id}/",
            {"order": 9},
            format="json",
        )
        assert resp.status_code in (403, 404)

    def test_duplicate_name_rejected(self, authed_client, project, section):
        resp = authed_client.post("/api/project-sections/", {
            "project": project.id,
            "name": section.name,
        }, format="json")
        assert resp.status_code == 400

    def test_delete(self, authed_client, section, task):
        task.section = section
        task.save(update_fields=["section"])
        resp = authed_client.delete(f"/api/project-sections/{section.id}/")
        assert resp.status_code == 204
        task.refresh_from_db()
        assert task.section_id is None  # SET_NULL


@pytest.mark.django_db
class TestSectionReorder:
    def test_reorder_assigns_sequential_order(self, authed_client, project):
        s1 = ProjectSection.objects.create(project=project, name="A", order=0)
        s2 = ProjectSection.objects.create(project=project, name="B", order=1)
        s3 = ProjectSection.objects.create(project=project, name="C", order=2)
        resp = authed_client.post("/api/project-sections/reorder/", {
            "project": project.id,
            "section_ids": [s3.id, s1.id, s2.id],
        }, format="json")
        assert resp.status_code == 200
        assert resp.data["updated"] == 3
        for s in (s1, s2, s3):
            s.refresh_from_db()
        assert (s3.order, s1.order, s2.order) == (0, 1, 2)

    def test_reorder_rejects_foreign_section(
        self, authed_client, user, project, section
    ):
        other_project = Project.objects.create(owner=user, name="Otro")
        foreign = ProjectSection.objects.create(
            project=other_project, name="Ajena"
        )
        resp = authed_client.post("/api/project-sections/reorder/", {
            "project": project.id,
            "section_ids": [section.id, foreign.id],
        }, format="json")
        assert resp.status_code == 400

    def test_reorder_requires_write_access(
        self, authed_client_other, other_user, project, section
    ):
        ProjectMember.objects.create(
            project=project, user=other_user, role="viewer"
        )
        resp = authed_client_other.post("/api/project-sections/reorder/", {
            "project": project.id,
            "section_ids": [section.id],
        }, format="json")
        assert resp.status_code in (403, 404)


# --- Task.section ---


@pytest.mark.django_db
class TestTaskSection:
    def test_patch_task_section(self, authed_client, task, section):
        resp = authed_client.patch(
            f"/api/tasks/{task.id}/",
            {"section": section.id},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["section"] == section.id
        assert resp.data["section_name"] == "Por hacer"
        task.refresh_from_db()
        assert task.section_id == section.id

    def test_create_task_with_section(self, authed_client, project, section):
        resp = authed_client.post("/api/tasks/", {
            "title": "Con sección",
            "project": project.id,
            "section": section.id,
        }, format="json")
        assert resp.status_code == 201
        assert resp.data["section_name"] == "Por hacer"

    def test_cross_project_section_rejected(
        self, authed_client, user, task
    ):
        other_project = Project.objects.create(owner=user, name="Otro")
        foreign_section = ProjectSection.objects.create(
            project=other_project, name="Ajena"
        )
        resp = authed_client.patch(
            f"/api/tasks/{task.id}/",
            {"section": foreign_section.id},
            format="json",
        )
        assert resp.status_code == 400
        task.refresh_from_db()
        assert task.section_id is None

    def test_section_without_project_rejected(self, authed_client, user):
        # Tarea en inbox (sin proyecto) no puede tener sección
        task = Task.objects.create(owner=user, title="Inbox task")
        section = ProjectSection.objects.create(
            project=Project.objects.create(owner=user, name="P"), name="S"
        )
        resp = authed_client.patch(
            f"/api/tasks/{task.id}/",
            {"section": section.id},
            format="json",
        )
        assert resp.status_code == 400

    def test_filter_tasks_by_section(
        self, authed_client, task, section, project
    ):
        task.section = section
        task.save(update_fields=["section"])
        Task.objects.create(
            owner=task.owner, project=project, title="Otra"
        )
        resp = authed_client.get(f"/api/tasks/?section={section.id}")
        assert resp.status_code == 200
        data = (
            resp.data["results"] if isinstance(resp.data, dict)
            else resp.data
        )
        assert len(data) == 1
        assert data[0]["id"] == task.id


# --- Refs legibles (issue_prefix + seq) ---


@pytest.mark.django_db
class TestTaskRefs:
    def test_prefix_derived_from_name(self, authed_client):
        resp = authed_client.post("/api/projects/", {
            "name": "Mi Proyecto",
        }, format="json")
        assert resp.status_code == 201
        assert resp.data["issue_prefix"] == "MP"

    def test_prefix_clamped_to_four(self, authed_client):
        resp = authed_client.post("/api/projects/", {
            "name": "Alpha Beta Gamma Delta Epsilon",
        }, format="json")
        assert resp.status_code == 201
        assert resp.data["issue_prefix"] == "ABGD"

    def test_provided_prefix_kept(self, authed_client):
        resp = authed_client.post("/api/projects/", {
            "name": "Mi Proyecto",
            "issue_prefix": "custom",
        }, format="json")
        assert resp.status_code == 201
        assert resp.data["issue_prefix"] == "custom"

    def test_seq_increments_per_project(self, authed_client, user):
        p1 = Project.objects.create(
            owner=user, name="Mi Proyecto", issue_prefix="MP"
        )
        r1 = authed_client.post("/api/tasks/", {
            "title": "t1", "project": p1.id,
        }, format="json")
        r2 = authed_client.post("/api/tasks/", {
            "title": "t2", "project": p1.id,
        }, format="json")
        assert r1.status_code == 201 and r2.status_code == 201
        assert r1.data["ref"] == "MP-1"
        assert r2.data["ref"] == "MP-2"
        assert (r1.data["seq"], r2.data["seq"]) == (1, 2)
        # Otro proyecto numera de forma independiente
        p2 = Project.objects.create(
            owner=user, name="Otra Cosa", issue_prefix="OC"
        )
        r3 = authed_client.post("/api/tasks/", {
            "title": "t3", "project": p2.id,
        }, format="json")
        assert r3.data["ref"] == "OC-1"
        assert r3.data["seq"] == 1

    def test_ref_falls_back_to_id_without_project(
        self, authed_client, user
    ):
        resp = authed_client.post("/api/tasks/", {
            "title": "sin proyecto",
        }, format="json")
        assert resp.status_code == 201
        assert resp.data["seq"] == 0
        assert resp.data["ref"] == str(resp.data["id"])


# --- Rollover de sprint ---


@pytest.mark.django_db
class TestSprintRollover:
    def test_close_moves_incomplete_to_next_sprint(
        self, authed_client, user, project, active_sprint, next_sprint
    ):
        t_open = Task.objects.create(
            owner=user, project=project, title="open",
            sprint=active_sprint, state=Task.State.IN_PROGRESS,
        )
        t_done = Task.objects.create(
            owner=user, project=project, title="done",
            sprint=active_sprint, state=Task.State.COMPLETED,
        )
        t_cancel = Task.objects.create(
            owner=user, project=project, title="cancel",
            sprint=active_sprint, state=Task.State.CANCELLED,
        )
        t_arch = Task.objects.create(
            owner=user, project=project, title="arch",
            sprint=active_sprint, state=Task.State.ARCHIVED,
        )
        resp = authed_client.post(
            f"/api/sprints/{active_sprint.id}/close/",
            {"move_incomplete_to": next_sprint.id},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["moved_incomplete"] == 1
        active_sprint.refresh_from_db()
        assert active_sprint.state == Sprint.SprintState.CLOSED
        for t, expected in (
            (t_open, next_sprint.id),
            (t_done, active_sprint.id),
            (t_cancel, active_sprint.id),
            (t_arch, active_sprint.id),
        ):
            t.refresh_from_db()
            assert t.sprint_id == expected

    def test_close_moves_incomplete_to_backlog(
        self, authed_client, user, project, active_sprint
    ):
        t_open = Task.objects.create(
            owner=user, project=project, title="open",
            sprint=active_sprint, state=Task.State.PENDING,
        )
        t_done = Task.objects.create(
            owner=user, project=project, title="done",
            sprint=active_sprint, state=Task.State.COMPLETED,
        )
        resp = authed_client.post(
            f"/api/sprints/{active_sprint.id}/close/",
            {"move_incomplete_to": "backlog"},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["moved_incomplete"] == 1
        t_open.refresh_from_db()
        t_done.refresh_from_db()
        assert t_open.sprint_id is None
        assert t_done.sprint_id == active_sprint.id

    def test_close_without_target_moves_nothing(
        self, authed_client, user, project, active_sprint
    ):
        t_open = Task.objects.create(
            owner=user, project=project, title="open",
            sprint=active_sprint, state=Task.State.PENDING,
        )
        resp = authed_client.post(
            f"/api/sprints/{active_sprint.id}/close/", {}, format="json"
        )
        assert resp.status_code == 200
        assert resp.data["moved_incomplete"] == 0
        t_open.refresh_from_db()
        assert t_open.sprint_id == active_sprint.id

    def test_close_rejects_foreign_sprint_target(
        self, authed_client, user, project, active_sprint
    ):
        other_project = Project.objects.create(owner=user, name="Otro")
        foreign = Sprint.objects.create(
            owner=user, project=other_project, name="Ajeno",
            state=Sprint.SprintState.PLANNED,
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=14),
        )
        resp = authed_client.post(
            f"/api/sprints/{active_sprint.id}/close/",
            {"move_incomplete_to": foreign.id},
            format="json",
        )
        assert resp.status_code == 400
        active_sprint.refresh_from_db()
        assert active_sprint.state == Sprint.SprintState.ACTIVE

    def test_close_rejects_self_target(
        self, authed_client, active_sprint
    ):
        resp = authed_client.post(
            f"/api/sprints/{active_sprint.id}/close/",
            {"move_incomplete_to": active_sprint.id},
            format="json",
        )
        assert resp.status_code == 400

    def test_close_rejects_invalid_target(
        self, authed_client, active_sprint
    ):
        resp = authed_client.post(
            f"/api/sprints/{active_sprint.id}/close/",
            {"move_incomplete_to": "no-existe"},
            format="json",
        )
        assert resp.status_code == 400
        resp = authed_client.post(
            f"/api/sprints/{active_sprint.id}/close/",
            {"move_incomplete_to": 999999},
            format="json",
        )
        assert resp.status_code == 404

    def test_close_non_active_still_rejected(
        self, authed_client, next_sprint
    ):
        resp = authed_client.post(
            f"/api/sprints/{next_sprint.id}/close/", {}, format="json"
        )
        assert resp.status_code == 400

    def test_legacy_next_sprint_id_still_works(
        self, authed_client, user, project, active_sprint, next_sprint
    ):
        t_open = Task.objects.create(
            owner=user, project=project, title="open",
            sprint=active_sprint, state=Task.State.PENDING,
        )
        resp = authed_client.post(
            f"/api/sprints/{active_sprint.id}/close/",
            {"next_sprint_id": next_sprint.id},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["moved_incomplete"] == 1
        t_open.refresh_from_db()
        assert t_open.sprint_id == next_sprint.id
