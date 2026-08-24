"""Tests de tareas: CRUD, permisos, filtros, estados, subtareas, comentarios."""
import pytest
from django.contrib.auth import get_user_model

from apps.tasks.models import Task

User = get_user_model()


@pytest.mark.django_db
class TestTaskCRUD:
    def test_crear_tarea(self, authed_client, project):
        resp = authed_client.post("/api/tasks/", {
            "title": "Nueva tarea",
            "description": "Descripción",
            "state": "pending",
            "priority": 2,
            "project": project.id,
        }, format="json")
        assert resp.status_code == 201
        assert resp.data["title"] == "Nueva tarea"
        assert resp.data["state"] == "pending"
        assert resp.data["priority"] == 2

    def test_crear_tarea_sin_proyecto(self, authed_client):
        resp = authed_client.post("/api/tasks/", {
            "title": "Tarea sin proyecto",
        }, format="json")
        assert resp.status_code == 201
        assert resp.data["project"] is None

    def test_listar_tareas(self, authed_client, task):
        resp = authed_client.get("/api/tasks/")
        assert resp.status_code == 200
        # Sin paginación en tests
        assert isinstance(resp.data, list)
        assert len(resp.data) == 1
        assert resp.data[0]["title"] == "Tarea de test"

    def test_obtener_tarea(self, authed_client, task):
        resp = authed_client.get(f"/api/tasks/{task.id}/")
        assert resp.status_code == 200
        assert resp.data["title"] == "Tarea de test"

    def test_actualizar_tarea(self, authed_client, task):
        resp = authed_client.patch(f"/api/tasks/{task.id}/", {
            "title": "Tarea modificada",
            "priority": 0,
        }, format="json")
        assert resp.status_code == 200
        assert resp.data["title"] == "Tarea modificada"
        assert resp.data["priority"] == 0

    def test_eliminar_tarea(self, authed_client, task):
        resp = authed_client.delete(f"/api/tasks/{task.id}/")
        assert resp.status_code == 204
        assert not Task.objects.filter(id=task.id).exists()

    def test_crear_tarea_sin_titulo(self, authed_client):
        resp = authed_client.post("/api/tasks/", {}, format="json")
        assert resp.status_code == 400


@pytest.mark.django_db
class TestTaskPermissions:
    def test_usuario_no_ve_tareas_de_otros(self, authed_client, other_user):
        Task.objects.create(owner=other_user, title="Tarea ajena")
        resp = authed_client.get("/api/tasks/")
        assert resp.status_code == 200
        assert len(resp.data) == 0

    def test_usuario_no_accede_tarea_ajena(self, authed_client, other_user):
        tarea_ajena = Task.objects.create(owner=other_user, title="Ajena")
        resp = authed_client.get(f"/api/tasks/{tarea_ajena.id}/")
        assert resp.status_code == 404

    def test_usuario_no_modifica_tarea_ajena(self, authed_client, other_user):
        tarea_ajena = Task.objects.create(owner=other_user, title="Ajena")
        resp = authed_client.patch(f"/api/tasks/{tarea_ajena.id}/", {
            "title": "Hackeada",
        }, format="json")
        assert resp.status_code == 404

    def test_usuario_no_elimina_tarea_ajena(self, authed_client, other_user):
        tarea_ajena = Task.objects.create(owner=other_user, title="Ajena")
        resp = authed_client.delete(f"/api/tasks/{tarea_ajena.id}/")
        assert resp.status_code == 404

    def test_tareas_sin_auth(self, api_client):
        resp = api_client.get("/api/tasks/")
        assert resp.status_code == 401

    def test_no_asigna_proyecto_ajeno(self, authed_client, other_user):
        from apps.projects.models import Project
        proyecto_ajeno = Project.objects.create(owner=other_user, name="Ajeno")
        resp = authed_client.post("/api/tasks/", {
            "title": "Tarea mía",
            "project": proyecto_ajeno.id,
        }, format="json")
        assert resp.status_code == 400

    def test_no_asigna_etiqueta_ajena(self, authed_client, other_user):
        from apps.tags.models import Tag
        tag_ajena = Tag.objects.create(owner=other_user, name="Ajena")
        resp = authed_client.post("/api/tasks/", {
            "title": "Tarea mía",
            "tags": [tag_ajena.id],
        }, format="json")
        assert resp.status_code == 400


@pytest.mark.django_db
class TestTaskFilters:
    def test_filtrar_por_estado(self, authed_client, user):
        Task.objects.create(owner=user, title="Pendiente", state="pending")
        Task.objects.create(owner=user, title="Completada", state="completed")
        resp = authed_client.get("/api/tasks/?state=pending")
        assert resp.status_code == 200
        assert len(resp.data) == 1
        assert resp.data[0]["title"] == "Pendiente"

    def test_filtrar_por_prioridad(self, authed_client, user):
        Task.objects.create(owner=user, title="Crítica", priority=0)
        Task.objects.create(owner=user, title="Baja", priority=4)
        resp = authed_client.get("/api/tasks/?priority=0")
        assert resp.status_code == 200
        assert len(resp.data) == 1
        assert resp.data[0]["title"] == "Crítica"

    def test_filtrar_por_proyecto(self, authed_client, user, project):
        Task.objects.create(owner=user, title="Con proyecto", project=project)
        Task.objects.create(owner=user, title="Sin proyecto", project=None)
        resp = authed_client.get(f"/api/tasks/?project={project.id}")
        assert resp.status_code == 200
        assert len(resp.data) == 1
        assert resp.data[0]["title"] == "Con proyecto"

    def test_buscar_por_texto(self, authed_client, user):
        Task.objects.create(owner=user, title="Comprar pan", description="")
        Task.objects.create(owner=user, title="Estudiar", description="")
        resp = authed_client.get("/api/tasks/?search=pan")
        assert resp.status_code == 200
        assert len(resp.data) == 1
        assert resp.data[0]["title"] == "Comprar pan"


@pytest.mark.django_db
class TestTaskCompletion:
    def test_completar_tarea_setea_completed_at(self, authed_client, task):
        resp = authed_client.patch(f"/api/tasks/{task.id}/", {
            "state": "completed",
        }, format="json")
        assert resp.status_code == 200
        task.refresh_from_db()
        assert task.completed_at is not None

    def test_reabrir_tarea_limpia_completed_at(self, authed_client, task):
        task.state = Task.State.COMPLETED
        task.completed_at = task.created_at
        task.save()
        resp = authed_client.patch(f"/api/tasks/{task.id}/", {
            "state": "pending",
        }, format="json")
        assert resp.status_code == 200
        task.refresh_from_db()
        assert task.completed_at is None


@pytest.mark.django_db
class TestSubtasks:
    def test_crear_subtarea(self, authed_client, task):
        resp = authed_client.post(f"/api/tasks/{task.id}/subtasks/", {
            "title": "Paso 1",
        }, format="json")
        assert resp.status_code == 201
        assert resp.data["title"] == "Paso 1"
        assert resp.data["is_done"] is False

    def test_subtareas_incluidas_en_tarea(self, authed_client, task):
        from apps.tasks.models import Subtask
        Subtask.objects.create(task=task, title="Paso 1")
        resp = authed_client.get(f"/api/tasks/{task.id}/")
        assert resp.status_code == 200
        assert len(resp.data["subtasks"]) == 1
        assert resp.data["subtasks"][0]["title"] == "Paso 1"


@pytest.mark.django_db
class TestComments:
    def test_crear_comentario(self, authed_client, task, user):
        resp = authed_client.post(f"/api/tasks/{task.id}/comments/", {
            "body": "Comentario de prueba",
        }, format="json")
        assert resp.status_code == 201
        assert resp.data["body"] == "Comentario de prueba"
        assert resp.data["author_email"] == user.email

    def test_comentarios_incluidos_en_tarea(self, authed_client, task):
        from apps.tasks.models import Comment
        Comment.objects.create(task=task, author=task.owner, body="Hola")
        resp = authed_client.get(f"/api/tasks/{task.id}/")
        assert resp.status_code == 200
        assert len(resp.data["comments"]) == 1
