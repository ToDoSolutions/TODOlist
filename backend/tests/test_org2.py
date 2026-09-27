"""Tests de la segunda tanda de features organizativas:

- Project health + ProjectStatusUpdate (estilo Asana)
- Capacidad semanal configurable por usuario (workload)
- Vinculación KeyResult <-> Task + linked_progress
- Cobertura de auditoría (AuditLog) para Task y Project
"""
import pytest

from apps.collaboration.models import AuditLog, ProjectMember
from apps.okrs.models import KeyResult, Objective
from apps.projects.models import Project, ProjectStatusUpdate
from apps.tasks.models import Task

# ---------------------------------------------------------------------------
# 1. Project health + status updates
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestProjectHealth:
    def test_patch_health_directo(self, authed_client, project):
        resp = authed_client.patch(
            f"/api/projects/{project.id}/", {"health": "at_risk"}, format="json"
        )
        assert resp.status_code == 200
        assert resp.data["health"] == "at_risk"
        project.refresh_from_db()
        assert project.health == "at_risk"

    def test_health_null_por_defecto(self, authed_client, project):
        resp = authed_client.get(f"/api/projects/{project.id}/")
        assert resp.status_code == 200
        assert resp.data["health"] is None
        assert resp.data["latest_status_update"] is None

    def test_health_invalido_falla(self, authed_client, project):
        resp = authed_client.patch(
            f"/api/projects/{project.id}/", {"health": "rainbow"}, format="json"
        )
        assert resp.status_code == 400


@pytest.mark.django_db
class TestProjectStatusUpdates:
    def test_crear_status_update_sincroniza_health(self, authed_client, project, user):
        resp = authed_client.post(
            "/api/project-status-updates/",
            {"project": project.id, "health": "off_track", "note": "Bloqueados por API"},
            format="json",
        )
        assert resp.status_code == 201
        assert resp.data["author"] == user.id
        assert resp.data["author_email"] == user.email
        assert resp.data["health"] == "off_track"
        assert resp.data["note"] == "Bloqueados por API"
        # El health del proyecto se sincroniza con el update
        project.refresh_from_db()
        assert project.health == "off_track"

    def test_health_directo_y_update_gana_el_update(self, authed_client, project):
        authed_client.patch(
            f"/api/projects/{project.id}/", {"health": "on_track"}, format="json"
        )
        authed_client.post(
            "/api/project-status-updates/",
            {"project": project.id, "health": "at_risk", "note": "n"},
            format="json",
        )
        project.refresh_from_db()
        assert project.health == "at_risk"

    def test_list_filtra_por_proyecto(self, authed_client, project, user):
        otro = Project.objects.create(owner=user, name="Otro")
        ProjectStatusUpdate.objects.create(
            project=project, author=user, health="on_track", note="a"
        )
        ProjectStatusUpdate.objects.create(
            project=otro, author=user, health="off_track", note="b"
        )
        resp = authed_client.get(
            f"/api/project-status-updates/?project={project.id}"
        )
        assert resp.status_code == 200
        assert len(resp.data) == 1
        assert resp.data[0]["health"] == "on_track"

    def test_scope_otro_usuario_no_ve_ni_crea(self, authed_client_other, other_user, project, user):
        # List: otros no ven updates de proyectos ajenos
        ProjectStatusUpdate.objects.create(
            project=project, author=user, health="on_track", note="x"
        )
        resp = authed_client_other.get(
            f"/api/project-status-updates/?project={project.id}"
        )
        assert resp.status_code == 200
        assert resp.data == []
        # Create: 403 (sin acceso de escritura al proyecto)
        resp = authed_client_other.post(
            "/api/project-status-updates/",
            {"project": project.id, "health": "on_track", "note": "hack"},
            format="json",
        )
        assert resp.status_code == 403

    def test_viewer_lee_pero_no_escribe(self, authed_client_other, other_user, project, user):
        ProjectMember.objects.create(
            project=project, user=other_user, role=ProjectMember.Role.VIEWER
        )
        ProjectStatusUpdate.objects.create(
            project=project, author=user, health="on_track", note="x"
        )
        # Viewer sí puede leer
        resp = authed_client_other.get(
            f"/api/project-status-updates/?project={project.id}"
        )
        assert resp.status_code == 200
        assert len(resp.data) == 1
        # Pero no crear
        resp = authed_client_other.post(
            "/api/project-status-updates/",
            {"project": project.id, "health": "off_track", "note": "n"},
            format="json",
        )
        assert resp.status_code == 403

    def test_editor_puede_crear(self, authed_client_other, other_user, project):
        ProjectMember.objects.create(
            project=project, user=other_user, role=ProjectMember.Role.EDITOR
        )
        resp = authed_client_other.post(
            "/api/project-status-updates/",
            {"project": project.id, "health": "at_risk", "note": "por editor"},
            format="json",
        )
        assert resp.status_code == 201
        project.refresh_from_db()
        assert project.health == "at_risk"

    def test_updates_son_inmutables(self, authed_client, project, user):
        update = ProjectStatusUpdate.objects.create(
            project=project, author=user, health="on_track", note="x"
        )
        resp = authed_client.patch(
            f"/api/project-status-updates/{update.id}/",
            {"health": "off_track"},
            format="json",
        )
        assert resp.status_code == 405
        resp = authed_client.put(
            f"/api/project-status-updates/{update.id}/",
            {"project": project.id, "health": "off_track"},
            format="json",
        )
        assert resp.status_code == 405

    def test_destroy_solo_autor(self, authed_client, authed_client_other, other_user, project, user):
        update = ProjectStatusUpdate.objects.create(
            project=project, author=user, health="on_track", note="x"
        )
        # Un editor del proyecto NO puede borrar el update ajeno (solo el autor)
        ProjectMember.objects.create(
            project=project, user=other_user, role=ProjectMember.Role.EDITOR
        )
        resp = authed_client_other.delete(
            f"/api/project-status-updates/{update.id}/"
        )
        assert resp.status_code == 404
        assert ProjectStatusUpdate.objects.filter(id=update.id).exists()
        # El autor sí
        resp = authed_client.delete(f"/api/project-status-updates/{update.id}/")
        assert resp.status_code == 204
        assert not ProjectStatusUpdate.objects.filter(id=update.id).exists()


@pytest.mark.django_db
class TestLatestStatusUpdateEnProject:
    def test_latest_status_update_en_retrieve(self, authed_client, project, user):
        ProjectStatusUpdate.objects.create(
            project=project, author=user, health="on_track", note="primera"
        )
        ultima = ProjectStatusUpdate.objects.create(
            project=project, author=user, health="at_risk", note="segunda"
        )
        resp = authed_client.get(f"/api/projects/{project.id}/")
        assert resp.status_code == 200
        lsu = resp.data["latest_status_update"]
        assert lsu["health"] == "at_risk"
        assert lsu["note"] == "segunda"
        assert lsu["author_email"] == user.email
        assert ultima.created_at.isoformat().startswith(
            lsu["created_at"][:19]
        )

    def test_latest_status_update_en_list(self, authed_client, project, user):
        ProjectStatusUpdate.objects.create(
            project=project, author=user, health="off_track", note="list"
        )
        resp = authed_client.get("/api/projects/")
        assert resp.status_code == 200
        assert resp.data[0]["latest_status_update"]["health"] == "off_track"

    def test_latest_status_update_null_sin_updates(self, authed_client, project):
        resp = authed_client.get(f"/api/projects/{project.id}/")
        assert resp.status_code == 200
        assert resp.data["latest_status_update"] is None


# ---------------------------------------------------------------------------
# 2. Capacidad semanal configurable
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestWeeklyCapacity:
    def test_default_40h(self, user):
        assert float(user.weekly_capacity_hours) == 40.0

    def test_patch_capacity_via_auth_me(self, authed_client, user):
        resp = authed_client.patch(
            "/api/auth/me/", {"weekly_capacity_hours": 20}, format="json"
        )
        assert resp.status_code == 200
        user.refresh_from_db()
        assert float(user.weekly_capacity_hours) == 20.0

    def test_me_expone_capacity(self, authed_client, user):
        resp = authed_client.get("/api/users/me/")
        assert resp.status_code == 200
        assert float(resp.data["weekly_capacity_hours"]) == 40.0

    def test_workload_usa_capacity_del_miembro(self, authed_client, user, project):
        user.weekly_capacity_hours = 20
        user.save(update_fields=["weekly_capacity_hours"])
        Task.objects.create(
            owner=user, project=project, title="T1",
            estimate_hours=10, state=Task.State.PENDING,
        )
        resp = authed_client.get("/api/tasks/workload/")
        assert resp.status_code == 200
        member = next(m for m in resp.data if m["user_id"] == user.id)
        assert member["capacity_hours"] == 20.0
        assert member["estimate_hours"] == 10.0
        # 10h estimadas / 20h capacidad = 50%
        assert member["utilization"] == 50

    def test_workload_default_40_sin_cambio(self, authed_client, user, project):
        Task.objects.create(
            owner=user, project=project, title="T1",
            estimate_hours=20, state=Task.State.PENDING,
        )
        resp = authed_client.get("/api/tasks/workload/")
        member = next(m for m in resp.data if m["user_id"] == user.id)
        assert member["capacity_hours"] == 40.0
        assert member["utilization"] == 50


# ---------------------------------------------------------------------------
# 3. KeyResult <-> Task linking
# ---------------------------------------------------------------------------


@pytest.fixture
def objective(user):
    return Objective.objects.create(
        owner=user, title="Objetivo", quarter="Q1", year=2026
    )


@pytest.fixture
def key_result(user, objective):
    return KeyResult.objects.create(
        owner=user, objective=objective, title="KR1", target_value=100
    )


@pytest.mark.django_db
class TestKeyResultLinkedTasks:
    def test_link_tasks_por_api(self, authed_client, key_result, user, project):
        t1 = Task.objects.create(owner=user, project=project, title="T1")
        t2 = Task.objects.create(owner=user, project=project, title="T2")
        resp = authed_client.patch(
            f"/api/key-results/{key_result.id}/",
            {"linked_tasks": [t1.id, t2.id]},
            format="json",
        )
        assert resp.status_code == 200
        assert set(resp.data["linked_tasks"]) == {t1.id, t2.id}
        detail = {d["id"]: d for d in resp.data["linked_tasks_detail"]}
        assert detail[t1.id]["title"] == "T1"
        assert detail[t2.id]["state"] == "pending"
        assert resp.data["linked_progress"] == 0

    def test_linked_progress_math(self, authed_client, key_result, user, project):
        t1 = Task.objects.create(
            owner=user, project=project, title="T1", state=Task.State.COMPLETED
        )
        t2 = Task.objects.create(
            owner=user, project=project, title="T2", state=Task.State.PENDING
        )
        authed_client.patch(
            f"/api/key-results/{key_result.id}/",
            {"linked_tasks": [t1.id, t2.id]},
            format="json",
        )
        resp = authed_client.get(f"/api/key-results/{key_result.id}/")
        assert resp.data["linked_progress"] == 50
        # Completar la segunda → 100%
        t2.state = Task.State.COMPLETED
        t2.save(update_fields=["state"])
        resp = authed_client.get(f"/api/key-results/{key_result.id}/")
        assert resp.data["linked_progress"] == 100

    def test_unlink_tasks(self, authed_client, key_result, user, project):
        t1 = Task.objects.create(owner=user, project=project, title="T1")
        authed_client.patch(
            f"/api/key-results/{key_result.id}/",
            {"linked_tasks": [t1.id]},
            format="json",
        )
        resp = authed_client.patch(
            f"/api/key-results/{key_result.id}/",
            {"linked_tasks": []},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["linked_tasks"] == []
        assert resp.data["linked_tasks_detail"] == []
        assert resp.data["linked_progress"] == 0

    def test_task_ajena_rechazada(self, authed_client, key_result, other_user, project):
        ajena = Task.objects.create(owner=other_user, title="Ajena")
        resp = authed_client.patch(
            f"/api/key-results/{key_result.id}/",
            {"linked_tasks": [ajena.id]},
            format="json",
        )
        assert resp.status_code == 400
        key_result.refresh_from_db()
        assert key_result.linked_tasks.count() == 0

    def test_task_compartida_es_vinculable(
        self, authed_client, key_result, other_user, user
    ):
        """Una tarea visible via for_user (proyecto donde soy miembro) linka."""
        proyecto_ajeno = Project.objects.create(owner=other_user, name="Ajeno")
        ProjectMember.objects.create(
            project=proyecto_ajeno, user=user, role=ProjectMember.Role.VIEWER
        )
        de_otro = Task.objects.create(
            owner=other_user, project=proyecto_ajeno, title="Compartida"
        )
        resp = authed_client.patch(
            f"/api/key-results/{key_result.id}/",
            {"linked_tasks": [de_otro.id]},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["linked_tasks"] == [de_otro.id]


# ---------------------------------------------------------------------------
# 4. Auditoría de Task y Project (create + delete via signals)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAuditTaskProject:
    def test_crear_tarea_registra_audit(self, authed_client, project, user):
        resp = authed_client.post(
            "/api/tasks/",
            {"title": "Tarea auditada", "project": project.id},
            format="json",
        )
        assert resp.status_code == 201
        task_id = resp.data["id"]
        log = AuditLog.objects.filter(
            action="create", resource_type="task", resource_id=task_id
        ).first()
        assert log is not None
        assert log.actor_id == user.id
        assert log.resource_name == "Tarea auditada"

    def test_borrar_tarea_registra_audit(self, authed_client, task, user):
        task_id = task.id
        AuditLog.objects.filter(
            resource_type="task", resource_id=task_id
        ).delete()
        resp = authed_client.delete(f"/api/tasks/{task_id}/")
        assert resp.status_code == 204
        log = AuditLog.objects.filter(
            action="delete", resource_type="task", resource_id=task_id
        ).first()
        assert log is not None
        assert log.actor_id == user.id
        assert log.resource_name == "Tarea de test"

    def test_crear_proyecto_registra_audit(self, authed_client, user):
        resp = authed_client.post(
            "/api/projects/", {"name": "Proyecto auditado"}, format="json"
        )
        assert resp.status_code == 201
        log = AuditLog.objects.filter(
            action="create",
            resource_type="project",
            resource_id=resp.data["id"],
        ).first()
        assert log is not None
        assert log.actor_id == user.id
        assert log.resource_name == "Proyecto auditado"

    def test_borrar_proyecto_registra_audit(self, authed_client, project, user):
        pid = project.id
        AuditLog.objects.filter(
            resource_type="project", resource_id=pid
        ).delete()
        resp = authed_client.delete(f"/api/projects/{pid}/")
        assert resp.status_code == 204
        log = AuditLog.objects.filter(
            action="delete", resource_type="project", resource_id=pid
        ).first()
        assert log is not None
        assert log.actor_id == user.id
        assert log.resource_name == "Proyecto Test"

    def test_update_no_genera_audit_via_signal(self, authed_client, project, user):
        """Decisión documentada: updates se auditan a nivel vista (patrón
        TeamViewSet); los signals solo cubren create + delete."""
        pid = project.id
        AuditLog.objects.filter(
            resource_type="project", resource_id=pid
        ).delete()
        authed_client.patch(
            f"/api/projects/{pid}/", {"name": "Renombrado"}, format="json"
        )
        assert not AuditLog.objects.filter(
            action="update", resource_type="project", resource_id=pid
        ).exists()
