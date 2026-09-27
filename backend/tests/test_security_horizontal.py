"""Tests de seguridad horizontal (IDOR): un usuario no puede acceder a
recursos de otro usuario mediante manipulación de IDs."""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.projects.models import Project
from apps.tasks.models import (
    Attachment,
    Comment,
    Epic,
    RecurrenceRule,
    Sprint,
    Task,
    TaskTemplate,
)


@pytest.fixture
def user_b(db):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create_user(
        email="user_b@test.com",
        username="user_b",
        password="testpass123",
    )


@pytest.fixture
def authed_client_b(user_b):
    """Cliente autenticado como user_b (instancia separada)."""
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import RefreshToken
    client = APIClient()
    refresh = RefreshToken.for_user(user_b)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return client


@pytest.mark.django_db
class TestTasksIDOR:
    """IDOR sobre tareas: usuario B no debe acceder a tareas de usuario A."""

    def test_usuario_b_no_ve_tarea_de_usuario_a(self, authed_client, authed_client_b, task):
        # Usuario A (authed_client) ve su tarea
        resp_a = authed_client.get(f"/api/tasks/{task.id}/")
        assert resp_a.status_code == 200
        # Usuario B no puede verla
        resp_b = authed_client_b.get(f"/api/tasks/{task.id}/")
        assert resp_b.status_code == 404

    def test_usuario_b_no_edita_tarea_de_usuario_a(self, authed_client_b, task):
        resp = authed_client_b.patch(f"/api/tasks/{task.id}/", {
            "title": "Hackeada por B",
        }, format="json")
        assert resp.status_code == 404
        task.refresh_from_db()
        assert task.title == "Tarea de test"

    def test_usuario_b_no_elimina_tarea_de_usuario_a(self, authed_client_b, task):
        resp = authed_client_b.delete(f"/api/tasks/{task.id}/")
        assert resp.status_code == 404
        assert Task.objects.filter(id=task.id).exists()

    def test_usuario_b_no_ve_tareas_de_a_en_listado(self, authed_client_b, task):
        resp = authed_client_b.get("/api/tasks/")
        assert resp.status_code == 200
        assert len(resp.data) == 0


@pytest.mark.django_db
class TestProjectsIDOR:
    """IDOR sobre proyectos: usuario B no debe acceder a proyectos de usuario A."""

    def test_usuario_b_no_ve_proyecto_de_usuario_a(self, authed_client, authed_client_b, project):
        resp_a = authed_client.get(f"/api/projects/{project.id}/")
        assert resp_a.status_code == 200
        resp_b = authed_client_b.get(f"/api/projects/{project.id}/")
        assert resp_b.status_code == 404

    def test_usuario_b_no_edita_proyecto_de_usuario_a(self, authed_client_b, project):
        resp = authed_client_b.patch(f"/api/projects/{project.id}/", {
            "name": "Hackeado por B",
        }, format="json")
        assert resp.status_code == 404
        project.refresh_from_db()
        assert project.name == "Proyecto Test"

    def test_usuario_b_no_elimina_proyecto_de_usuario_a(self, authed_client_b, project):
        resp = authed_client_b.delete(f"/api/projects/{project.id}/")
        assert resp.status_code == 404
        assert Project.objects.filter(id=project.id).exists()

    def test_usuario_b_no_ve_proyectos_de_a_en_listado(self, authed_client_b, project):
        resp = authed_client_b.get("/api/projects/")
        assert resp.status_code == 200
        assert len(resp.data) == 0


@pytest.mark.django_db
class TestCommentsIDOR:
    """IDOR sobre comentarios: usuario B no debe editar/eliminar comentarios
    de tareas que pertenecen a usuario A."""

    def test_usuario_b_no_edita_comentario_de_usuario_a(self, authed_client, authed_client_b, task, user):
        comentario = Comment.objects.create(task=task, author=user, body="Comentario de A")
        resp = authed_client_b.patch(f"/api/comments/{comentario.id}/", {
            "body": "Hackeado por B",
        }, format="json")
        assert resp.status_code == 404
        comentario.refresh_from_db()
        assert comentario.body == "Comentario de A"

    def test_usuario_b_no_elimina_comentario_de_usuario_a(self, authed_client_b, task, user):
        comentario = Comment.objects.create(task=task, author=user, body="Comentario de A")
        resp = authed_client_b.delete(f"/api/comments/{comentario.id}/")
        assert resp.status_code == 404
        assert Comment.objects.filter(id=comentario.id).exists()

    def test_usuario_b_no_ve_comentarios_de_a_en_listado(self, authed_client_b, task, user):
        Comment.objects.create(task=task, author=user, body="Comentario de A")
        resp = authed_client_b.get("/api/comments/")
        assert resp.status_code == 200
        assert len(resp.data) == 0


@pytest.mark.django_db
class TestAttachmentsIDOR:
    """IDOR sobre adjuntos: usuario B no debe ver ni eliminar adjuntos
    de tareas que pertenecen a usuario A."""

    def test_usuario_b_no_ve_adjuntos_de_a_en_listado(self, authed_client_b, task, user):
        adjunto = Attachment.objects.create(
            task=task,
            uploaded_by=user,
            file=SimpleUploadedFile("doc.txt", b"contenido"),
            filename="doc.txt",
        )
        resp = authed_client_b.get("/api/attachments/")
        assert resp.status_code == 200
        # Usuario B no es owner de la tarea ni subió el adjunto
        ids = [a["id"] for a in resp.data]
        assert adjunto.id not in ids

    def test_usuario_b_no_elimina_adjunto_de_usuario_a(self, authed_client_b, task, user):
        adjunto = Attachment.objects.create(
            task=task,
            uploaded_by=user,
            file=SimpleUploadedFile("doc.txt", b"contenido"),
            filename="doc.txt",
        )
        resp = authed_client_b.delete(f"/api/attachments/{adjunto.id}/")
        assert resp.status_code == 404
        assert Attachment.objects.filter(id=adjunto.id).exists()


@pytest.mark.django_db
class TestSprintsIDOR:
    """IDOR sobre sprints: usuario B no debe acceder a sprints de usuario A."""

    def test_usuario_b_no_ve_sprint_de_usuario_a(self, authed_client, authed_client_b, user, project):
        sprint = Sprint.objects.create(
            owner=user, name="Sprint A", start_date="2025-01-01", end_date="2025-01-14",
        )
        resp_a = authed_client.get(f"/api/sprints/{sprint.id}/")
        assert resp_a.status_code == 200
        resp_b = authed_client_b.get(f"/api/sprints/{sprint.id}/")
        assert resp_b.status_code == 404

    def test_usuario_b_no_edita_sprint_de_usuario_a(self, authed_client_b, user):
        sprint = Sprint.objects.create(
            owner=user, name="Sprint A", start_date="2025-01-01", end_date="2025-01-14",
        )
        resp = authed_client_b.patch(f"/api/sprints/{sprint.id}/", {
            "name": "Hackeado por B",
        }, format="json")
        assert resp.status_code == 404
        sprint.refresh_from_db()
        assert sprint.name == "Sprint A"

    def test_usuario_b_no_ve_sprints_de_a_en_listado(self, authed_client_b, user):
        Sprint.objects.create(
            owner=user, name="Sprint A", start_date="2025-01-01", end_date="2025-01-14",
        )
        resp = authed_client_b.get("/api/sprints/")
        assert resp.status_code == 200
        assert len(resp.data) == 0


@pytest.mark.django_db
class TestEpicsIDOR:
    """IDOR sobre épicas: usuario B no debe acceder a épicas de usuario A."""

    def test_usuario_b_no_ve_epica_de_usuario_a(self, authed_client, authed_client_b, user):
        epic = Epic.objects.create(owner=user, title="Épica A")
        resp_a = authed_client.get(f"/api/epics/{epic.id}/")
        assert resp_a.status_code == 200
        resp_b = authed_client_b.get(f"/api/epics/{epic.id}/")
        assert resp_b.status_code == 404

    def test_usuario_b_no_edita_epica_de_usuario_a(self, authed_client_b, user):
        epic = Epic.objects.create(owner=user, title="Épica A")
        resp = authed_client_b.patch(f"/api/epics/{epic.id}/", {
            "title": "Hackeado por B",
        }, format="json")
        assert resp.status_code == 404
        epic.refresh_from_db()
        assert epic.title == "Épica A"

    def test_usuario_b_no_ve_epicas_de_a_en_listado(self, authed_client_b, user):
        Epic.objects.create(owner=user, title="Épica A")
        resp = authed_client_b.get("/api/epics/")
        assert resp.status_code == 200
        assert len(resp.data) == 0


@pytest.mark.django_db
class TestTaskTemplatesIDOR:
    """IDOR sobre plantillas de tareas: usuario B no debe acceder a plantillas
    de usuario A."""

    def test_usuario_b_no_ve_plantilla_de_usuario_a(self, authed_client, authed_client_b, user):
        template = TaskTemplate.objects.create(
            owner=user, name="Plantilla A", template_data={"title": "Tarea base"},
        )
        resp_a = authed_client.get(f"/api/task-templates/{template.id}/")
        assert resp_a.status_code == 200
        resp_b = authed_client_b.get(f"/api/task-templates/{template.id}/")
        assert resp_b.status_code == 404

    def test_usuario_b_no_edita_plantilla_de_usuario_a(self, authed_client_b, user):
        template = TaskTemplate.objects.create(
            owner=user, name="Plantilla A", template_data={"title": "Tarea base"},
        )
        resp = authed_client_b.patch(f"/api/task-templates/{template.id}/", {
            "name": "Hackeado por B",
        }, format="json")
        assert resp.status_code == 404
        template.refresh_from_db()
        assert template.name == "Plantilla A"

    def test_usuario_b_no_ve_plantillas_de_a_en_listado(self, authed_client_b, user):
        TaskTemplate.objects.create(
            owner=user, name="Plantilla A", template_data={"title": "Tarea base"},
        )
        resp = authed_client_b.get("/api/task-templates/")
        assert resp.status_code == 200
        assert len(resp.data) == 0


@pytest.mark.django_db
class TestRecurrenceRuleIDOR:
    """IDOR sobre reglas de recurrencia: usuario B no debe acceder a reglas
    de usuario A."""

    def test_usuario_b_no_ve_regla_de_usuario_a(self, authed_client, authed_client_b, user):
        regla = RecurrenceRule.objects.create(
            owner=user, frequency="daily", interval=1,
        )
        resp_a = authed_client.get(f"/api/recurrence-rules/{regla.id}/")
        assert resp_a.status_code == 200
        resp_b = authed_client_b.get(f"/api/recurrence-rules/{regla.id}/")
        assert resp_b.status_code == 404

    def test_usuario_b_no_edita_regla_de_usuario_a(self, authed_client_b, user):
        regla = RecurrenceRule.objects.create(
            owner=user, frequency="daily", interval=1,
        )
        resp = authed_client_b.patch(f"/api/recurrence-rules/{regla.id}/", {
            "frequency": "weekly",
        }, format="json")
        assert resp.status_code == 404
        regla.refresh_from_db()
        assert regla.frequency == "daily"

    def test_usuario_b_no_ve_reglas_de_a_en_listado(self, authed_client_b, user):
        RecurrenceRule.objects.create(owner=user, frequency="daily", interval=1)
        resp = authed_client_b.get("/api/recurrence-rules/")
        assert resp.status_code == 200
        assert len(resp.data) == 0
