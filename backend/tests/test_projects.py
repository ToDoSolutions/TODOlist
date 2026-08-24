"""Tests de proyectos y etiquetas: CRUD, permisos, archivado."""
import pytest
from apps.projects.models import Project
from apps.tags.models import Tag


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
