"""Tests de workflows configurables por proyecto (WorkflowTransition)."""
from unittest.mock import Mock

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.graphql_app.schema import schema
from apps.projects.models import Project, WorkflowTransition
from apps.tasks.models import Task

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="w", email="w@w.com", password="p")


@pytest.fixture
def project(user):
    return Project.objects.create(owner=user, name="P")


def _client(u):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(u).access_token}")
    return c


@pytest.mark.django_db
class TestWorkflowEnforcement:
    def test_sin_workflow_cambio_libre(self, user, project):
        t = Task.objects.create(owner=user, project=project, title="T")
        resp = _client(user).patch(f"/api/tasks/{t.id}/", {"state": "completed"})
        assert resp.status_code == 200
        t.refresh_from_db()
        assert t.state == "completed"

    def test_con_workflow_transicion_valida(self, user, project):
        WorkflowTransition.objects.create(
            project=project, from_state="pending", to_state="in_progress")
        WorkflowTransition.objects.create(
            project=project, from_state="in_progress", to_state="completed")
        t = Task.objects.create(
            owner=user, project=project, title="T", state="pending")
        resp = _client(user).patch(f"/api/tasks/{t.id}/", {"state": "in_progress"})
        assert resp.status_code == 200

    def test_con_workflow_transicion_invalida_rechazada(self, user, project):
        # Solo pending → in_progress definido: pending → completed prohibido
        WorkflowTransition.objects.create(
            project=project, from_state="pending", to_state="in_progress")
        t = Task.objects.create(
            owner=user, project=project, title="T", state="pending")
        resp = _client(user).patch(f"/api/tasks/{t.id}/", {"state": "completed"})
        assert resp.status_code == 400
        t.refresh_from_db()
        assert t.state == "pending"

    def test_workflow_aplica_en_graphql(self, user, project):
        WorkflowTransition.objects.create(
            project=project, from_state="pending", to_state="in_progress")
        t = Task.objects.create(
            owner=user, project=project, title="T", state="pending")
        info = Mock()
        info.context.user = user
        result = schema.execute(
            f'mutation {{ updateTask(id: {t.id}, state: "completed") {{ task {{ state }} }} }}',
            context=info.context,
        )
        assert result.errors is not None
        t.refresh_from_db()
        assert t.state == "pending"

    def test_workflow_aplica_en_bulk(self, user, project):
        WorkflowTransition.objects.create(
            project=project, from_state="pending", to_state="in_progress")
        t = Task.objects.create(
            owner=user, project=project, title="T", state="pending")
        resp = _client(user).post("/api/tasks/bulk_update/", {
            "task_ids": [t.id], "updates": {"state": "completed"},
        }, format="json")
        assert resp.status_code == 400

    def test_workflow_no_afecta_otros_proyectos(self, user, project):
        otro = Project.objects.create(owner=user, name="Otro")
        WorkflowTransition.objects.create(
            project=otro, from_state="pending", to_state="in_progress")
        t = Task.objects.create(
            owner=user, project=project, title="T", state="pending")
        resp = _client(user).patch(f"/api/tasks/{t.id}/", {"state": "completed"})
        assert resp.status_code == 200


@pytest.mark.django_db
class TestWorkflowTransitionAPI:
    def test_crud(self, user, project):
        c = _client(user)
        resp = c.post("/api/workflow-transitions/", {
            "project": project.id,
            "from_state": "pending",
            "to_state": "in_progress",
        })
        assert resp.status_code == 201

    def test_estado_invalido(self, user, project):
        resp = _client(user).post("/api/workflow-transitions/", {
            "project": project.id,
            "from_state": "pending",
            "to_state": "bogus",
        })
        assert resp.status_code == 400

    def test_mismo_estado_rechazado(self, user, project):
        resp = _client(user).post("/api/workflow-transitions/", {
            "project": project.id,
            "from_state": "pending",
            "to_state": "pending",
        })
        assert resp.status_code == 400

    def test_proyecto_ajeno_rechazado(self, user, project):
        outsider = User.objects.create_user(username="x", email="x@x.com", password="p")
        resp = _client(outsider).post("/api/workflow-transitions/", {
            "project": project.id,
            "from_state": "pending",
            "to_state": "in_progress",
        })
        assert resp.status_code == 400
