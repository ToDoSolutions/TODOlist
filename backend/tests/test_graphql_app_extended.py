"""Tests exhaustivos para graphql_app."""
from unittest.mock import MagicMock

import pytest
from django.contrib.auth import get_user_model
from graphene.test import Client

from apps.graphql_app.schema import schema
from apps.projects.models import Project
from apps.tasks.models import Task

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="gql", email="gql@gql.com", password="pass")


@pytest.fixture
def project(user, db):
    return Project.objects.create(owner=user, name="Test Project")


@pytest.fixture
def client():
    return Client(schema)


def _mock_request(user):
    request = MagicMock()
    request.user = user
    return request


@pytest.mark.django_db
class TestGraphQLQueries:
    def test_all_tasks(self, client, user, project):
        Task.objects.create(owner=user, project=project, title="Task 1")
        result = client.execute(
            "{ allTasks { id title } }",
            context=_mock_request(user),
        )
        assert "errors" not in result
        assert len(result["data"]["allTasks"]) == 1
        assert result["data"]["allTasks"][0]["title"] == "Task 1"

    def test_all_tasks_unauthenticated(self, client):
        request = MagicMock()
        request.user = MagicMock()
        request.user.is_authenticated = False
        result = client.execute(
            "{ allTasks { id title } }",
            context=request,
        )
        assert "errors" in result
        assert "Authentication required" in str(result["errors"])

    def test_task(self, client, user, project):
        task = Task.objects.create(owner=user, project=project, title="Task 1")
        result = client.execute(
            f'{{ task(id: {task.id}) {{ id title }} }}',
            context=_mock_request(user),
        )
        assert "errors" not in result
        assert result["data"]["task"]["title"] == "Task 1"

    def test_task_not_found(self, client, user):
        result = client.execute(
            '{ task(id: 999) { id title } }',
            context=_mock_request(user),
        )
        assert result["data"]["task"] is None

    def test_all_projects(self, client, user, project):
        result = client.execute(
            "{ allProjects { id name } }",
            context=_mock_request(user),
        )
        assert "errors" not in result
        assert len(result["data"]["allProjects"]) == 1
        assert result["data"]["allProjects"][0]["name"] == "Test Project"

    def test_all_projects_unauthenticated(self, client):
        request = MagicMock()
        request.user = MagicMock()
        request.user.is_authenticated = False
        result = client.execute(
            "{ allProjects { id name } }",
            context=request,
        )
        assert "errors" in result


@pytest.mark.django_db
class TestGraphQLMutations:
    def test_create_task(self, client, user, project):
        result = client.execute(
            f'mutation {{ createTask(title: "New Task", projectId: {project.id}) {{ task {{ id title }} }} }}',
            context=_mock_request(user),
        )
        assert "errors" not in result
        assert result["data"]["createTask"]["task"]["title"] == "New Task"
        assert Task.objects.filter(title="New Task").exists()

    def test_create_task_invalid_project(self, client, user):
        result = client.execute(
            'mutation { createTask(title: "New Task", projectId: 999) { task { id title } } }',
            context=_mock_request(user),
        )
        assert "errors" in result

    def test_update_task(self, client, user, project):
        task = Task.objects.create(owner=user, project=project, title="Task 1")
        result = client.execute(
            f'mutation {{ updateTask(id: {task.id}, title: "Updated") {{ task {{ id title }} }} }}',
            context=_mock_request(user),
        )
        assert "errors" not in result
        assert result["data"]["updateTask"]["task"]["title"] == "Updated"
        task.refresh_from_db()
        assert task.title == "Updated"

    def test_delete_task(self, client, user, project):
        task = Task.objects.create(owner=user, project=project, title="Task 1")
        result = client.execute(
            f'mutation {{ deleteTask(id: {task.id}) {{ success }} }}',
            context=_mock_request(user),
        )
        assert "errors" not in result
        assert result["data"]["deleteTask"]["success"] is True
        assert not Task.objects.filter(id=task.id).exists()
