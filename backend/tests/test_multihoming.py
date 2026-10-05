"""Multi-homing: una tarea vive en su proyecto canónico y en
``extra_projects`` — aparece al filtrar por ambos y sus miembros
obtienen acceso según su rol allí."""
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.collaboration.models import ProjectMember
from apps.projects.models import Project
from apps.tasks.models import Task

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture
def owner(db):
    return User.objects.create_user(email="o@t.dev", username="o", password="x" * 20)


@pytest.fixture
def member(db):
    return User.objects.create_user(email="m@t.dev", username="m", password="x" * 20)


@pytest.fixture
def outsider(db):
    return User.objects.create_user(email="x@t.dev", username="x", password="x" * 20)


@pytest.fixture
def projects(owner):
    return (
        Project.objects.create(owner=owner, name="A"),
        Project.objects.create(owner=owner, name="B"),
    )


def _auth(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


class TestExtraProjects:
    def test_task_appears_in_extra_project_filter(self, owner, projects):
        a, b = projects
        task = Task.objects.create(owner=owner, project=a, title="H")
        task.extra_projects.add(b)
        ids = [
            t["id"] for t in _auth(owner).get(f"/api/tasks/?project={b.id}").json()
        ]
        assert task.id in ids
        ids_a = [
            t["id"] for t in _auth(owner).get(f"/api/tasks/?project={a.id}").json()
        ]
        assert task.id in ids_a

    def test_member_of_extra_project_reads(self, owner, member, projects):
        a, b = projects
        ProjectMember.objects.create(project=b, user=member, role="viewer")
        task = Task.objects.create(owner=owner, project=a, title="H")
        task.extra_projects.add(b)
        r = _auth(member).get(f"/api/tasks/{task.id}/")
        assert r.status_code == 200

    def test_editor_of_extra_project_writes(self, owner, member, projects):
        a, b = projects
        ProjectMember.objects.create(project=b, user=member, role="editor")
        task = Task.objects.create(owner=owner, project=a, title="H")
        task.extra_projects.add(b)
        r = _auth(member).patch(f"/api/tasks/{task.id}/", {"title": "X"})
        assert r.status_code == 200

    def test_viewer_of_extra_project_cannot_write(self, owner, member, projects):
        a, b = projects
        ProjectMember.objects.create(project=b, user=member, role="viewer")
        task = Task.objects.create(owner=owner, project=a, title="H")
        task.extra_projects.add(b)
        r = _auth(member).patch(f"/api/tasks/{task.id}/", {"title": "X"})
        assert r.status_code in (403, 404)

    def test_outsider_404(self, owner, outsider, projects):
        a, b = projects
        task = Task.objects.create(owner=owner, project=a, title="H")
        task.extra_projects.add(b)
        r = _auth(outsider).get(f"/api/tasks/{task.id}/")
        assert r.status_code == 404

    def test_set_extra_projects_via_api(self, owner, projects):
        a, b = projects
        r = _auth(owner).post(
            "/api/tasks/",
            {"title": "H", "project": a.id, "extra_projects": [b.id]},
            format="json",
        )
        assert r.status_code == 201
        task = Task.objects.get(title="H")
        assert list(task.extra_projects.all()) == [b]

    def test_canonical_rejected_as_extra(self, owner, projects):
        a, _ = projects
        r = _auth(owner).post(
            "/api/tasks/",
            {"title": "H", "project": a.id, "extra_projects": [a.id]},
            format="json",
        )
        assert r.status_code == 400
        assert "extra_projects" in r.json()

    def test_extra_project_requires_write_access(self, owner, outsider, projects):
        """Un usuario no puede homear una tarea en un proyecto ajeno."""
        _, b = projects
        t = Task.objects.create(owner=outsider, title="H")
        r = _auth(outsider).patch(
            f"/api/tasks/{t.id}/",
            {"extra_projects": [b.id]},
            format="json",
        )
        assert r.status_code == 400

    def test_serialized_in_detail(self, owner, projects):
        a, b = projects
        task = Task.objects.create(owner=owner, project=a, title="H")
        task.extra_projects.add(b)
        r = _auth(owner).get(f"/api/tasks/{task.id}/")
        assert r.status_code == 200
        assert r.json()["extra_projects"] == [b.id]

    def test_recurrence_keeps_extra_homes(self, owner, projects):
        """La siguiente ocurrencia hereda los hogares extra."""
        from apps.tasks.models import RecurrenceRule
        a, b = projects
        task = Task.objects.create(owner=owner, project=a, title="R")
        task.extra_projects.add(b)
        task.recurrence = RecurrenceRule.objects.create(
            owner=owner, frequency="daily"
        )
        nxt = task.generate_next_occurrence()
        assert nxt is not None
        assert nxt.project_id == a.id
        assert list(nxt.extra_projects.values_list("id", flat=True)) == [b.id]


class TestProjectDeleteRehomes:
    """Borrar un proyecto no debe borrar las tareas multi-homeadas: el
    primer hogar extra pasa a canónico soltando las relaciones del
    proyecto borrado (sprint/epic/section/seq)."""

    def test_multihomed_task_is_rehomed_not_deleted(self, owner, projects):
        import datetime

        from apps.projects.models import ProjectSection
        from apps.tasks.models import Epic, Sprint

        a, b = projects
        sprint = Sprint.objects.create(
            owner=owner, project=a, name="S1",
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 1, 14),
        )
        epic = Epic.objects.create(owner=owner, project=a, title="E1")
        section = ProjectSection.objects.create(project=a, name="Sec")
        task = Task.objects.create(
            owner=owner, project=a, title="H",
            sprint=sprint, epic=epic, section=section, seq=7,
        )
        task.extra_projects.add(b)
        only_a = Task.objects.create(owner=owner, project=a, title="Solo A")

        r = _auth(owner).delete(f"/api/projects/{a.id}/")
        assert r.status_code == 204

        task.refresh_from_db()
        assert task.project_id == b.id
        assert task.sprint_id is None
        assert task.epic_id is None
        assert task.section_id is None
        assert task.seq == 0
        assert not task.extra_projects.exists()
        # La tarea solo-homeada sí se borra con el proyecto
        assert not Task.objects.filter(id=only_a.id).exists()


class TestBulkUpdateProjectCoherence:
    """bulk_update con cambio de proyecto debe mantener las invariantes del
    proyecto canónico (misma regla que el PATCH individual): sprint/epic/
    section de otro proyecto se sueltan y el destino no puede quedar como
    hogar extra."""

    def test_project_change_drops_stale_links_and_extra_home(self, owner, projects):
        import datetime

        from apps.projects.models import ProjectSection
        from apps.tasks.models import Epic, Sprint

        a, b = projects
        sprint = Sprint.objects.create(
            owner=owner, project=a, name="S1",
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 1, 14),
        )
        epic = Epic.objects.create(owner=owner, project=a, title="E1")
        section = ProjectSection.objects.create(project=a, name="Sec")
        task = Task.objects.create(
            owner=owner, project=a, title="H",
            sprint=sprint, epic=epic, section=section,
        )
        task.extra_projects.add(b)
        r = _auth(owner).post(
            "/api/tasks/bulk_update/",
            {"task_ids": [task.id], "updates": {"project": b.id}},
            format="json",
        )
        assert r.status_code == 200
        task.refresh_from_db()
        assert task.project_id == b.id
        assert task.sprint_id is None
        assert task.epic_id is None
        assert task.section_id is None
        assert not task.extra_projects.exists()

    def test_explicit_sprint_of_other_project_rejected(self, owner, projects):
        import datetime

        from apps.tasks.models import Sprint

        a, b = projects
        sprint_b = Sprint.objects.create(
            owner=owner, project=b, name="S2",
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 1, 14),
        )
        task = Task.objects.create(owner=owner, project=a, title="H")
        r = _auth(owner).post(
            "/api/tasks/bulk_update/",
            {"task_ids": [task.id], "updates": {"sprint": sprint_b.id}},
            format="json",
        )
        assert r.status_code == 400
        task.refresh_from_db()
        assert task.sprint_id is None

    def test_project_and_matching_sprint_move(self, owner, projects):
        import datetime

        from apps.tasks.models import Sprint

        a, b = projects
        sprint_b = Sprint.objects.create(
            owner=owner, project=b, name="S2",
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 1, 14),
        )
        task = Task.objects.create(owner=owner, project=a, title="H")
        r = _auth(owner).post(
            "/api/tasks/bulk_update/",
            {
                "task_ids": [task.id],
                "updates": {"project": b.id, "sprint": sprint_b.id},
            },
            format="json",
        )
        assert r.status_code == 200
        task.refresh_from_db()
        assert task.project_id == b.id
        assert task.sprint_id == sprint_b.id

class TestWsRecipients:
    """El push WS debe llegar a todos los que pueden ver la tarea:
    watchers, assignees y miembros de hogares extra (incl. org)."""

    def test_assignee_and_watcher_receive_push(
        self, owner, member, outsider, projects
    ):
        from apps.tasks.ws_signals import _task_recipients

        a, _b = projects
        task = Task.objects.create(owner=owner, project=a, title="H")
        task.assignees.add(member)
        task.watchers.add(outsider)
        ids = _task_recipients(task)
        assert {owner.id, member.id, outsider.id} <= ids

    def test_extra_project_org_members_receive_push(
        self, owner, member, projects
    ):
        from apps.collaboration.models import (
            Organization,
            OrganizationMembership,
        )
        from apps.tasks.ws_signals import _task_recipients

        a, b = projects
        org = Organization.objects.create(owner=member, name="Org")
        OrganizationMembership.objects.create(
            organization=org, user=member,
            role=OrganizationMembership.Role.MEMBER,
        )
        b.organization = org
        b.save(update_fields=["organization"])
        task = Task.objects.create(owner=owner, project=a, title="H")
        task.extra_projects.add(b)
        assert member.id in _task_recipients(task)
