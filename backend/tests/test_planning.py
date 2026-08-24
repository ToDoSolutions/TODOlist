"""Tests de fases 2-4: jerarquías, relaciones, actividad, sprints, épicas, búsquedas guardadas."""
import pytest
from datetime import date, timedelta
from django.utils import timezone

from apps.tasks.models import (
    Task, TaskRelation, TaskActivity, Sprint, Epic, SavedSearch,
)


@pytest.fixture
def sprint(user):
    return Sprint.objects.create(
        owner=user,
        name="Sprint 1",
        goal="Entregar MVP",
        start_date=date.today(),
        end_date=date.today() + timedelta(days=14),
    )


@pytest.fixture
def epic(user):
    return Epic.objects.create(owner=user, title="Epica MVP", color="#ff0000")


@pytest.mark.django_db
class TestSprints:
    def test_crear_sprint(self, authed_client):
        resp = authed_client.post("/api/sprints/", {
            "name": "Sprint Test",
            "goal": "Probar sprints",
            "start_date": "2025-01-01",
            "end_date": "2025-01-15",
        }, format="json")
        assert resp.status_code == 201
        assert resp.data["name"] == "Sprint Test"
        assert resp.data["state"] == "planned"

    def test_listar_sprints(self, authed_client, sprint):
        resp = authed_client.get("/api/sprints/")
        assert resp.status_code == 200
        data = resp.data["results"] if "results" in resp.data else resp.data
        assert len(data) == 1
        assert data[0]["name"] == "Sprint 1"

    def test_sprint_activo(self, authed_client, sprint):
        sprint.state = Sprint.SprintState.ACTIVE
        sprint.save()
        resp = authed_client.get("/api/sprints/active/")
        assert resp.status_code == 200
        assert resp.data["name"] == "Sprint 1"

    def test_no_sprint_activo(self, authed_client, sprint):
        resp = authed_client.get("/api/sprints/active/")
        assert resp.status_code == 200
        assert resp.data is None

    def test_cerrar_sprint(self, authed_client, sprint, user):
        sprint.state = Sprint.SprintState.ACTIVE
        sprint.save()
        # Crear tarea incompleta en el sprint
        Task.objects.create(
            owner=user, title="Tarea incompleta",
            state=Task.State.IN_PROGRESS, sprint=sprint,
        )
        # Crear siguiente sprint
        next_sprint = Sprint.objects.create(
            owner=user, name="Sprint 2",
            start_date=date.today() + timedelta(days=15),
            end_date=date.today() + timedelta(days=29),
        )
        resp = authed_client.post(
            f"/api/sprints/{sprint.id}/close/",
            {"next_sprint_id": next_sprint.id},
            format="json",
        )
        assert resp.status_code == 200
        sprint.refresh_from_db()
        assert sprint.state == "closed"
        # La tarea incompleta debe haberse movido
        task = Task.objects.get(title="Tarea incompleta")
        assert task.sprint_id == next_sprint.id

    def test_tareas_de_sprint(self, authed_client, sprint, user):
        Task.objects.create(owner=user, title="T1", sprint=sprint)
        Task.objects.create(owner=user, title="T2", sprint=sprint)
        resp = authed_client.get(f"/api/sprints/{sprint.id}/tasks/")
        assert resp.status_code == 200
        data = resp.data["results"] if "results" in resp.data else resp.data
        assert len(data) == 2

    def test_sprint_ajeno_no_visible(self, authed_client, other_user):
        Sprint.objects.create(
            owner=other_user, name="Ajeno",
            start_date=date.today(), end_date=date.today() + timedelta(days=7),
        )
        resp = authed_client.get("/api/sprints/")
        data = resp.data["results"] if "results" in resp.data else resp.data
        assert len(data) == 0


@pytest.mark.django_db
class TestEpics:
    def test_crear_epica(self, authed_client):
        resp = authed_client.post("/api/epics/", {
            "title": "Nueva epica",
            "description": "Desc",
            "color": "#123456",
        }, format="json")
        assert resp.status_code == 201
        assert resp.data["title"] == "Nueva epica"

    def test_progreso_epica(self, authed_client, epic, user):
        Task.objects.create(owner=user, title="T1", epic=epic, state=Task.State.COMPLETED)
        Task.objects.create(owner=user, title="T2", epic=epic, state=Task.State.PENDING)
        Task.objects.create(owner=user, title="T3", epic=epic, state=Task.State.IN_PROGRESS)
        resp = authed_client.get(f"/api/epics/{epic.id}/")
        assert resp.status_code == 200
        assert resp.data["progress_done"] == 1
        assert resp.data["progress_total"] == 3

    def test_tareas_de_epica(self, authed_client, epic, user):
        Task.objects.create(owner=user, title="T1", epic=epic)
        resp = authed_client.get(f"/api/epics/{epic.id}/tasks/")
        assert resp.status_code == 200
        data = resp.data["results"] if "results" in resp.data else resp.data
        assert len(data) == 1


@pytest.mark.django_db
class TestHierarchies:
    def test_crear_tarea_con_padre(self, authed_client, user):
        parent = Task.objects.create(owner=user, title="Padre")
        resp = authed_client.post("/api/tasks/", {
            "title": "Hija",
            "parent": parent.id,
        }, format="json")
        assert resp.status_code == 201
        assert resp.data["parent"] == parent.id

    def test_progreso_subtareas(self, authed_client, user):
        parent = Task.objects.create(owner=user, title="Padre")
        Task.objects.create(owner=user, title="H1", parent=parent, state=Task.State.COMPLETED)
        Task.objects.create(owner=user, title="H2", parent=parent, state=Task.State.PENDING)
        resp = authed_client.get(f"/api/tasks/{parent.id}/")
        assert resp.data["subtask_done"] == 1
        assert resp.data["subtask_total"] == 2

    def test_evitar_ciclo_jerarquia(self, authed_client, user):
        parent = Task.objects.create(owner=user, title="Padre")
        child = Task.objects.create(owner=user, title="Hija", parent=parent)
        # Intentar hacer que parent sea hijo de child → ciclo
        resp = authed_client.patch(f"/api/tasks/{parent.id}/", {
            "parent": child.id,
        }, format="json")
        assert resp.status_code == 400

    def test_evitar_auto_referencia(self, authed_client, user):
        task = Task.objects.create(owner=user, title="Tarea")
        resp = authed_client.patch(f"/api/tasks/{task.id}/", {
            "parent": task.id,
        }, format="json")
        assert resp.status_code == 400


@pytest.mark.django_db
class TestRelations:
    def test_crear_relacion(self, authed_client, user):
        t1 = Task.objects.create(owner=user, title="T1")
        t2 = Task.objects.create(owner=user, title="T2")
        resp = authed_client.post(f"/api/tasks/{t1.id}/relations/", {
            "target": t2.id,
            "relation_type": "blocks",
        }, format="json")
        assert resp.status_code == 201
        assert resp.data["relation_type"] == "blocks"

    def test_listar_relaciones(self, authed_client, user):
        t1 = Task.objects.create(owner=user, title="T1")
        t2 = Task.objects.create(owner=user, title="T2")
        TaskRelation.objects.create(source=t1, target=t2, relation_type="blocks")
        resp = authed_client.get(f"/api/tasks/{t1.id}/relations/")
        assert resp.status_code == 200
        assert len(resp.data) == 1

    def test_relacion_a_tarea_ajena(self, authed_client, user, other_user):
        t1 = Task.objects.create(owner=user, title="T1")
        t2 = Task.objects.create(owner=other_user, title="T2 ajena")
        resp = authed_client.post(f"/api/tasks/{t1.id}/relations/", {
            "target": t2.id,
            "relation_type": "blocks",
        }, format="json")
        assert resp.status_code == 400


@pytest.mark.django_db
class TestActivity:
    def test_actividad_creacion(self, authed_client, user):
        resp = authed_client.post("/api/tasks/", {
            "title": "Nueva tarea",
        }, format="json")
        task_id = resp.data["id"]
        activities = TaskActivity.objects.filter(task_id=task_id)
        assert activities.count() >= 1
        assert activities.first().action == "created"

    def test_actividad_cambio_estado(self, authed_client, user):
        task = Task.objects.create(owner=user, title="T", state=Task.State.PENDING)
        authed_client.patch(f"/api/tasks/{task.id}/", {
            "state": "in_progress",
        }, format="json")
        activities = TaskActivity.objects.filter(
            task=task, action="state_changed"
        )
        assert activities.count() == 1
        assert activities.first().old_value == "pending"
        assert activities.first().new_value == "in_progress"

    def test_listar_actividades(self, authed_client, user):
        # Crear via API para que se registre actividad
        resp = authed_client.post("/api/tasks/", {"title": "T"}, format="json")
        task_id = resp.data["id"]
        resp = authed_client.get(f"/api/tasks/{task_id}/activities/")
        assert resp.status_code == 200
        assert len(resp.data) >= 1


@pytest.mark.django_db
class TestSavedSearches:
    def test_crear_busqueda_guardada(self, authed_client):
        resp = authed_client.post("/api/saved-searches/", {
            "name": "Mis bugs",
            "filters": {"state": "pending", "task_type": "bug"},
        }, format="json")
        assert resp.status_code == 201
        assert resp.data["name"] == "Mis bugs"

    def test_listar_busquedas_propias(self, authed_client, user):
        SavedSearch.objects.create(
            owner=user, name="Busqueda 1",
            filters={"state": "pending"},
        )
        resp = authed_client.get("/api/saved-searches/")
        assert resp.status_code == 200
        data = resp.data["results"] if "results" in resp.data else resp.data
        assert len(data) == 1

    def test_busquedas_compartidas_visibles(self, authed_client, other_user):
        SavedSearch.objects.create(
            owner=other_user, name="Compartida",
            filters={"state": "pending"}, is_shared=True,
        )
        resp = authed_client.get("/api/saved-searches/")
        data = resp.data["results"] if "results" in resp.data else resp.data
        assert any(d["name"] == "Compartida" for d in data)


@pytest.mark.django_db
class TestTaskTypesAndEstimates:
    def test_crear_tarea_con_tipo_y_estimacion(self, authed_client):
        resp = authed_client.post("/api/tasks/", {
            "title": "Bug critico",
            "task_type": "bug",
            "story_points": 8,
            "estimate_hours": 16.5,
            "size": "l",
        }, format="json")
        assert resp.status_code == 201, f"Error: {resp.data}"
        assert resp.data["task_type"] == "bug"
        assert resp.data["story_points"] == 8

    def test_filtrar_por_tipo(self, authed_client, user):
        Task.objects.create(owner=user, title="Bug", task_type="bug")
        Task.objects.create(owner=user, title="Feature", task_type="feature")
        resp = authed_client.get("/api/tasks/?task_type=bug")
        data = resp.data["results"] if "results" in resp.data else resp.data
        assert len(data) == 1
        assert data[0]["task_type"] == "bug"

    def test_filtrar_por_sprint(self, authed_client, user, sprint):
        Task.objects.create(owner=user, title="En sprint", sprint=sprint)
        Task.objects.create(owner=user, title="Fuera sprint")
        resp = authed_client.get(f"/api/tasks/?sprint={sprint.id}")
        data = resp.data["results"] if "results" in resp.data else resp.data
        assert len(data) == 1

    def test_mover_a_sprint(self, authed_client, user, sprint):
        task = Task.objects.create(owner=user, title="T")
        resp = authed_client.post(f"/api/tasks/{task.id}/move_to_sprint/", {
            "sprint_id": sprint.id,
        }, format="json")
        assert resp.status_code == 200
        task.refresh_from_db()
        assert task.sprint_id == sprint.id
