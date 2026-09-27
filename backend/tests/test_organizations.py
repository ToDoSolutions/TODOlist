"""Tests de Organization (tenant raíz) y propagación de acceso a proyectos."""
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.collaboration.models import Organization, OrganizationMembership
from apps.projects.models import Project, accessible_projects
from apps.tasks.models import Task

User = get_user_model()


@pytest.fixture
def owner(db):
    return User.objects.create_user(username="o", email="o@o.com", password="p")


@pytest.fixture
def member(db):
    return User.objects.create_user(username="m", email="m@m.com", password="p")


@pytest.fixture
def admin(db):
    return User.objects.create_user(username="a", email="a@a.com", password="p")


@pytest.fixture
def org(owner, member, admin):
    o = Organization.objects.create(name="Acme", owner=owner)
    OrganizationMembership.objects.create(
        organization=o, user=owner, role="owner")
    OrganizationMembership.objects.create(
        organization=o, user=member, role="member")
    OrganizationMembership.objects.create(
        organization=o, user=admin, role="admin")
    return o


@pytest.fixture
def org_project(owner, org):
    return Project.objects.create(
        owner=owner, name="OrgProj", organization=org)


def _client(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return c


@pytest.mark.django_db
class TestOrgAccessPropagation:
    def test_member_lectura_proyecto_org(self, org_project, member):
        assert accessible_projects(member).filter(id=org_project.id).exists()
        assert not accessible_projects(member, write=True).filter(id=org_project.id).exists()

    def test_admin_escritura_proyecto_org(self, org_project, admin):
        assert accessible_projects(admin, write=True).filter(id=org_project.id).exists()

    def test_guest_sin_acceso(self, org_project, org):
        guest = User.objects.create_user(username="g", email="g@g.com", password="p")
        OrganizationMembership.objects.create(
            organization=org, user=guest, role="guest")
        assert not accessible_projects(guest).filter(id=org_project.id).exists()

    def test_member_ve_tareas_del_proyecto_org(self, org_project, member, owner):
        t = Task.objects.create(owner=owner, project=org_project, title="OrgTask")
        assert Task.objects.for_user(member).filter(id=t.id).exists()
        # member solo lectura
        assert not Task.objects.for_user(member, write=True).filter(id=t.id).exists()

    def test_admin_edita_tareas_del_proyecto_org(self, org_project, admin, owner):
        t = Task.objects.create(owner=owner, project=org_project, title="OrgTask")
        assert Task.objects.for_user(admin, write=True).filter(id=t.id).exists()

    def test_usuario_externo_sin_acceso(self, org_project):
        outsider = User.objects.create_user(username="x", email="x@x.com", password="p")
        assert not accessible_projects(outsider).filter(id=org_project.id).exists()

    def test_proyecto_sin_org_sin_propagacion(self, owner, member):
        p = Project.objects.create(owner=owner, name="Personal")
        assert not accessible_projects(member).filter(id=p.id).exists()


@pytest.mark.django_db
class TestOrganizationAPI:
    def test_crear_org_asigna_owner(self, owner):
        resp = _client(owner).post("/api/organizations/", {"name": "Acme"})
        assert resp.status_code == 201
        org = Organization.objects.get(name="Acme")
        assert OrganizationMembership.objects.filter(
            organization=org, user=owner, role="owner").exists()

    def test_member_no_puede_editar_org(self, org, member):
        resp = _client(member).patch(
            f"/api/organizations/{org.id}/", {"name": "Hackeado"})
        assert resp.status_code == 403

    def test_admin_anade_miembro(self, org, admin):
        nuevo = User.objects.create_user(username="n", email="n@n.com", password="p")
        resp = _client(admin).post(
            f"/api/organizations/{org.id}/add_member/",
            {"email": "n@n.com", "role": "member"})
        assert resp.status_code == 200
        assert OrganizationMembership.objects.filter(user=nuevo).exists()

    def test_member_no_anade_miembros(self, org, member):
        resp = _client(member).post(
            f"/api/organizations/{org.id}/add_member/",
            {"email": "x@x.com"})
        assert resp.status_code == 403

    def test_org_audita_creacion(self, owner):
        from apps.collaboration.models import AuditLog
        _client(owner).post("/api/organizations/", {"name": "AuditOrg"})
        assert AuditLog.objects.filter(
            resource_type="organization", action="create").exists()

    def test_org_audita_borrado(self, org, owner):
        from apps.collaboration.models import AuditLog
        _client(owner).delete(f"/api/organizations/{org.id}/")
        assert AuditLog.objects.filter(
            resource_type="organization", action="delete").exists()
