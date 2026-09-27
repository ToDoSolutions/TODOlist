"""Tests exhaustivos para tasks/views.py (parte 2)."""
import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from apps.projects.models import Project
from apps.tasks.models import Sprint, Task

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="tv", email="tv@tv.com", password="pass")


@pytest.fixture
def api_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def project(user, db):
    return Project.objects.create(owner=user, name="Test Project")


@pytest.mark.django_db
class TestTaskViewSetExtended:
    def test_metrics_dashboard(self, api_client, user, project):
        """Verifica que metrics_dashboard retorna datos."""
        Task.objects.create(owner=user, project=project, title="Task 1")
        response = api_client.get("/api/tasks/metrics_dashboard/")
        assert response.status_code == status.HTTP_200_OK
        assert "open" in response.data

    def test_burndown_missing_sprint(self, api_client):
        """Verifica que burndown requiere sprint_id."""
        response = api_client.get("/api/tasks/burndown/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "sprint_id" in response.data["error"]

    def test_burndown_invalid_sprint(self, api_client):
        """Verifica que burndown retorna 404 si sprint no existe."""
        response = api_client.get("/api/tasks/burndown/?sprint_id=999")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_capacity(self, api_client, user, project):
        """Verifica que capacity retorna datos."""
        Task.objects.create(owner=user, project=project, title="Task 1")
        response = api_client.get("/api/tasks/capacity/")
        assert response.status_code == status.HTTP_200_OK

    def test_audit_dashboard(self, api_client, user, project):
        """Verifica que audit_dashboard retorna datos."""
        Task.objects.create(owner=user, project=project, title="Task 1")
        response = api_client.get("/api/tasks/audit_dashboard/")
        assert response.status_code == status.HTTP_200_OK

    def test_bulk_delete(self, api_client, user, project):
        """Verifica que bulk_delete elimina tareas."""
        t1 = Task.objects.create(owner=user, project=project, title="Task 1")
        t2 = Task.objects.create(owner=user, project=project, title="Task 2")
        response = api_client.post("/api/tasks/bulk_delete/", {"task_ids": [t1.id, t2.id]}, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["deleted"] == 2
        assert not Task.objects.filter(id__in=[t1.id, t2.id]).exists()

    def test_bulk_delete_empty(self, api_client):
        """Verifica que bulk_delete requiere task_ids."""
        response = api_client.post("/api/tasks/bulk_delete/", {}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_bulk_delete_other_user(self, api_client):
        """Verifica que bulk_delete no elimina tareas de otros usuarios."""
        other = User.objects.create_user(username="other", email="other@other.com", password="pass")
        project = Project.objects.create(owner=other, name="Other Project")
        task = Task.objects.create(owner=other, project=project, title="Other Task")
        response = api_client.post("/api/tasks/bulk_delete/", {"task_ids": [task.id]}, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["deleted"] == 0
        assert Task.objects.filter(id=task.id).exists()

    def test_bulk_move_sprint(self, api_client, user, project):
        """Verifica que bulk_move_sprint mueve tareas a sprint."""
        sprint = Sprint.objects.create(
            owner=user, project=project, name="Sprint 1", state="active",
            start_date="2024-01-01", end_date="2024-01-14"
        )
        t1 = Task.objects.create(owner=user, project=project, title="Task 1")
        t2 = Task.objects.create(owner=user, project=project, title="Task 2")
        response = api_client.post("/api/tasks/bulk_move_sprint/", {
            "task_ids": [t1.id, t2.id], "sprint_id": sprint.id
        }, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["moved"] == 2
        t1.refresh_from_db()
        assert t1.sprint == sprint

    def test_bulk_move_sprint_missing(self, api_client):
        """Verifica que bulk_move_sprint requiere task_ids y sprint_id."""
        response = api_client.post("/api/tasks/bulk_move_sprint/", {}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
