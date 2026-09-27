"""Tests de proyectos y etiquetas: CRUD, permisos, archivado."""
import pytest

from apps.projects.models import Project
from apps.tags.models import Tag
from apps.tasks.models import Task


@pytest.mark.django_db
class TestProjectCRUD:
    def test_crear_proyecto(self, authed_client):
        resp = authed_client.post("/api/projects/", {
            "name": "Mi proyecto",
            "description": "Desc",
            "color": "#1976d2",
        }, format="json")
        assert resp.status_code == 201
        assert resp.data["name"] == "Mi proyecto"

    def test_listar_proyectos(self, authed_client, project):
        resp = authed_client.get("/api/projects/")
        assert resp.status_code == 200
        assert isinstance(resp.data, list)
        assert len(resp.data) == 1

    def test_actualizar_proyecto(self, authed_client, project):
        resp = authed_client.patch(f"/api/projects/{project.id}/", {
            "name": "Renombrado",
        }, format="json")
        assert resp.status_code == 200
        assert resp.data["name"] == "Renombrado"

    def test_eliminar_proyecto(self, authed_client, project):
        resp = authed_client.delete(f"/api/projects/{project.id}/")
        assert resp.status_code == 204
        assert not Project.objects.filter(id=project.id).exists()

    def test_eliminar_proyecto_con_tareas(self, authed_client, project, task):
        """Regresión: el post_delete de la tarea accedía a task.project cuando
        el proyecto ya estaba borrado (cascade) → DoesNotExist → 500."""
        resp = authed_client.delete(f"/api/projects/{project.id}/")
        assert resp.status_code == 204
        assert not Project.objects.filter(id=project.id).exists()
        assert not Task.objects.filter(id=task.id).exists()

    def test_proyectos_sin_auth(self, api_client):
        resp = api_client.get("/api/projects/")
        assert resp.status_code == 401


@pytest.mark.django_db
class TestProjectPermissions:
    def test_no_ve_proyectos_ajenos(self, authed_client, other_user):
        Project.objects.create(owner=other_user, name="Ajeno")
        resp = authed_client.get("/api/projects/")
        assert resp.status_code == 200
        assert len(resp.data) == 0

    def test_no_modifica_proyecto_ajeno(self, authed_client, other_user):
        ajeno = Project.objects.create(owner=other_user, name="Ajeno")
        resp = authed_client.patch(f"/api/projects/{ajeno.id}/", {
            "name": "Hackeado",
        }, format="json")
        assert resp.status_code == 404


@pytest.mark.django_db
class TestProjectArchive:
    def test_archivados_no_aparecen_por_defecto(self, authed_client, user):
        Project.objects.create(owner=user, name="Activo")
        Project.objects.create(owner=user, name="Archivado", is_archived=True)
        resp = authed_client.get("/api/projects/")
        assert resp.status_code == 200
        assert len(resp.data) == 1
        assert resp.data[0]["name"] == "Activo"

    def test_ver_archivados_con_parametro(self, authed_client, user):
        Project.objects.create(owner=user, name="Archivado", is_archived=True)
        resp = authed_client.get("/api/projects/?archived=true")
        assert resp.status_code == 200
        assert len(resp.data) == 1


@pytest.mark.django_db
class TestProjectModelMutationKills:
    def test_nombre_muy_largo_falla(self, authed_client):
        resp = authed_client.post("/api/projects/", {
            "name": "x" * 121,
        }, format="json")
        assert resp.status_code == 400

    def test_descripcion_opcional(self, authed_client, user):
        resp = authed_client.post("/api/projects/", {
            "name": "Sin descripcion",
        }, format="json")
        assert resp.status_code == 201
        project = Project.objects.get(id=resp.data["id"])
        assert project.description == ""
        project.full_clean()  # verifica blank=True

    def test_color_default(self, authed_client, user):
        resp = authed_client.post("/api/projects/", {
            "name": "Color default",
        }, format="json")
        assert resp.status_code == 201
        project = Project.objects.get(id=resp.data["id"])
        assert project.color == "#1976d2"

    def test_color_invalido_falla(self, authed_client):
        resp = authed_client.post("/api/projects/", {
            "name": "Color invalido",
            "color": "#1234567",
        }, format="json")
        assert resp.status_code == 400

    def test_related_name_projects(self, user):
        Project.objects.create(owner=user, name="P1")
        Project.objects.create(owner=user, name="P2")
        assert user.projects.count() == 2

    def test_proyectos_ordenados_por_fecha(self, authed_client, user):
        from django.utils import timezone
        p1 = Project.objects.create(owner=user, name="Primero")
        p2 = Project.objects.create(owner=user, name="Segundo")
        # auto_now_add ignora created_at en create(): fijar vía update
        Project.objects.filter(pk=p1.pk).update(created_at=timezone.now() - timezone.timedelta(hours=2))
        Project.objects.filter(pk=p2.pk).update(created_at=timezone.now() - timezone.timedelta(hours=1))
        resp = authed_client.get("/api/projects/")
        assert resp.status_code == 200
        assert [p["name"] for p in resp.data] == ["Segundo", "Primero"]

    def test_updated_at_se_actualiza(self, authed_client, project):
        old_updated_at = project.updated_at
        import time
        time.sleep(0.01)
        resp = authed_client.patch(f"/api/projects/{project.id}/", {
            "name": "Renombrado",
        }, format="json")
        assert resp.status_code == 200
        project.refresh_from_db()
        assert project.updated_at > old_updated_at

    def test_campos_solo_lectura(self, authed_client, project):
        from apps.projects.serializers import ProjectSerializer
        assert "id" in ProjectSerializer.Meta.read_only_fields
        assert "created_at" in ProjectSerializer.Meta.read_only_fields
        assert "updated_at" in ProjectSerializer.Meta.read_only_fields


@pytest.mark.django_db
class TestTagCRUD:
    def test_crear_etiqueta(self, authed_client):
        resp = authed_client.post("/api/tags/", {
            "name": "Urgente",
            "color": "#e53935",
        }, format="json")
        assert resp.status_code == 201
        assert resp.data["name"] == "Urgente"

    def test_listar_etiquetas(self, authed_client, tag):
        resp = authed_client.get("/api/tags/")
        assert resp.status_code == 200
        assert isinstance(resp.data, list)
        assert len(resp.data) == 1

    def test_eliminar_etiqueta(self, authed_client, tag):
        resp = authed_client.delete(f"/api/tags/{tag.id}/")
        assert resp.status_code == 204
        assert not Tag.objects.filter(id=tag.id).exists()

    def test_etiquetas_sin_auth(self, api_client):
        resp = api_client.get("/api/tags/")
        assert resp.status_code == 401


@pytest.mark.django_db
class TestTagPermissions:
    def test_no_ve_etiquetas_ajenas(self, authed_client, other_user):
        Tag.objects.create(owner=other_user, name="Ajena")
        resp = authed_client.get("/api/tags/")
        assert resp.status_code == 200
        assert len(resp.data) == 0
