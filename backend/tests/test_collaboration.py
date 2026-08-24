"""Tests de Fase 10 (colaboración) y Fase 11 (audit)."""
import pytest
from datetime import date, timedelta
from django.utils import timezone

from apps.tasks.models import Task, Comment
from apps.users.models import User
from apps.notifications.models import Notification
from apps.collaboration.models import (
    Team, TeamMembership, ProjectMember, Mention, AuditLog,
)
from apps.collaboration.mentions import extract_mentions, process_mentions
from apps.collaboration.audit import (
    log_action, log_create, log_update, log_delete, log_role_change,
)


# --- Fase 10: Colaboración ---

@pytest.mark.django_db
class TestTeams:
    def test_crear_equipo(self, authed_client, user):
        resp = authed_client.post("/api/teams/", {
            "name": "Mi equipo",
            "description": "Equipo de desarrollo",
        }, format="json")
        assert resp.status_code == 201
        assert resp.data["name"] == "Mi equipo"
        # El creador debe ser owner
        team = Team.objects.get(name="Mi equipo")
        membership = TeamMembership.objects.get(team=team, user=user)
        assert membership.role == "owner"

    def test_listar_equipos(self, authed_client, user):
        team = Team.objects.create(name="T1", slug="t1", owner=user)
        TeamMembership.objects.create(team=team, user=user, role="owner")
        resp = authed_client.get("/api/teams/")
        assert resp.status_code == 200
        data = resp.data["results"] if "results" in resp.data else resp.data
        assert len(data) == 1

    def test_añadir_miembro(self, authed_client, user, other_user):
        team = Team.objects.create(name="T1", slug="t1", owner=user)
        TeamMembership.objects.create(team=team, user=user, role="owner")
        resp = authed_client.post(
            f"/api/teams/{team.id}/members/",
            {"user_id": other_user.id, "role": "member"},
            format="json",
        )
        assert resp.status_code == 201
        assert TeamMembership.objects.filter(team=team, user=other_user).exists()

    def test_eliminar_miembro(self, authed_client, user, other_user):
        team = Team.objects.create(name="T1", slug="t1", owner=user)
        m = TeamMembership.objects.create(team=team, user=other_user, role="member")
        resp = authed_client.delete(f"/api/teams/{team.id}/members/{m.id}/")
        assert resp.status_code == 204
        assert not TeamMembership.objects.filter(id=m.id).exists()


@pytest.mark.django_db
class TestProjectMembers:
    def test_invitar_a_proyecto(self, authed_client, user, other_user, project):
        resp = authed_client.post("/api/project-members/invite/", {
            "email": other_user.email,
            "project_id": project.id,
            "role": "editor",
        }, format="json")
        assert resp.status_code == 201
        assert ProjectMember.objects.filter(project=project, user=other_user).exists()

    def test_invitar_usuario_inexistente(self, authed_client, project):
        resp = authed_client.post("/api/project-members/invite/", {
            "email": "noexiste@test.com",
            "project_id": project.id,
        }, format="json")
        assert resp.status_code == 404

    def test_listar_miembros(self, authed_client, user, project):
        ProjectMember.objects.create(project=project, user=user, role="owner")
        resp = authed_client.get("/api/project-members/")
        assert resp.status_code == 200


@pytest.mark.django_db
class TestMentions:
    def test_extraer_menciones(self):
        text = "Hola @alice revisa esto @bob por favor"
        mentions = extract_mentions(text)
        assert "alice" in mentions
        assert "bob" in mentions

    def test_extraer_menciones_vacio(self):
        assert extract_mentions("Sin menciones") == set()

    def test_procesar_menciones_crea_notificacion(self, user, other_user, task):
        mentioned = process_mentions(
            text=f"Hola @{other_user.username} revisa esto",
            task=task,
            mentioned_by=user,
        )
        assert len(mentioned) == 1
        assert mentioned[0] == other_user
        # Debe crear una mención
        assert Mention.objects.filter(mentioned_user=other_user).count() == 1
        # Debe crear una notificación
        assert Notification.objects.filter(
            recipient=other_user, type="mention"
        ).count() == 1

    def test_no_mencionarse_a_si_mismo(self, user, task):
        mentioned = process_mentions(
            text=f"Hola @{user.username}",
            task=task,
            mentioned_by=user,
        )
        assert len(mentioned) == 0

    def test_mencion_por_comentario(self, user, other_user, task):
        """Al crear un comentario con @user, se procesa la mención."""
        Comment.objects.create(
            task=task, author=user,
            body=f"Revisa esto @{other_user.username}",
        )
        assert Mention.objects.filter(mentioned_user=other_user).count() == 1
        assert Notification.objects.filter(
            recipient=other_user, type="mention"
        ).count() == 1


@pytest.mark.django_db
class TestMentionAPI:
    def test_listar_menciones_recibidas(self, authed_client, user, other_user, task):
        Mention.objects.create(
            task=task, mentioned_user=user, mentioned_by=other_user,
        )
        resp = authed_client.get("/api/mentions/")
        assert resp.status_code == 200
        data = resp.data["results"] if "results" in resp.data else resp.data
        assert len(data) == 1


# --- Fase 11: Audit Log ---

@pytest.mark.django_db
class TestAuditLog:
    def test_log_create(self, user):
        entry = log_create(
            actor=user, resource_type="task", resource_id=1,
            resource_name="Mi tarea", new_values={"title": "Mi tarea"},
        )
        assert entry is not None
        assert entry.action == "create"
        assert entry.resource_type == "task"
        assert entry.actor == user

    def test_log_update(self, user):
        entry = log_update(
            actor=user, resource_type="task", resource_id=1,
            resource_name="Mi tarea",
            old_values={"state": "pending"},
            new_values={"state": "completed"},
        )
        assert entry.action == "update"
        assert entry.old_values == {"state": "pending"}
        assert entry.new_values == {"state": "completed"}

    def test_log_delete(self, user):
        entry = log_delete(
            actor=user, resource_type="project", resource_id=1,
            resource_name="Mi proyecto",
            old_values={"name": "Mi proyecto"},
        )
        assert entry.action == "delete"

    def test_log_role_change(self, user, other_user):
        entry = log_role_change(
            actor=user, target_user=other_user,
            old_role="viewer", new_role="editor",
            resource_type="project", resource_id=1,
        )
        assert entry.action == "role_change"
        assert entry.old_values == {"role": "viewer"}
        assert entry.new_values == {"role": "editor"}


@pytest.mark.django_db
class TestAuditLogAPI:
    def test_listar_audit_logs(self, authed_client, user):
        log_create(actor=user, resource_type="task", resource_id=1, resource_name="T1")
        log_update(actor=user, resource_type="task", resource_id=1, resource_name="T1")
        resp = authed_client.get("/api/audit-logs/")
        assert resp.status_code == 200
        data = resp.data["results"] if "results" in resp.data else resp.data
        assert len(data) == 2

    def test_filtrar_por_accion(self, authed_client, user):
        log_create(actor=user, resource_type="task", resource_id=1, resource_name="T1")
        log_delete(actor=user, resource_type="task", resource_id=2, resource_name="T2")
        resp = authed_client.get("/api/audit-logs/?action=delete")
        assert resp.status_code == 200
        data = resp.data["results"] if "results" in resp.data else resp.data
        assert len(data) == 1
        assert data[0]["action"] == "delete"

    def test_filtrar_por_resource_type(self, authed_client, user):
        log_create(actor=user, resource_type="task", resource_id=1, resource_name="T1")
        log_create(actor=user, resource_type="project", resource_id=1, resource_name="P1")
        resp = authed_client.get("/api/audit-logs/?resource_type=project")
        assert resp.status_code == 200
        data = resp.data["results"] if "results" in resp.data else resp.data
        assert len(data) == 1
        assert data[0]["resource_type"] == "project"
