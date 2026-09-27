from unittest.mock import Mock

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.graphql_app.schema import schema
from apps.projects.models import Project
from apps.tags.models import Tag
from apps.tasks.models import Task

User = get_user_model()


@pytest.mark.django_db
class TestGraphQLQueries:
    @pytest.fixture(autouse=True)
    def setup_data(self, db):
        self.user = User.objects.create_user(username="g", email="g@g.com", password="pass")
        self.project = Project.objects.create(owner=self.user, name="P1")
        self.task = Task.objects.create(owner=self.user, project=self.project, title="T1", state="pending")
        self.tag = Tag.objects.create(owner=self.user, name="bug")

    def test_all_tasks(self):
        info = Mock()
        info.context.user = self.user
        result = schema.execute("{ allTasks { id title state } }", context=info.context)
        assert not result.errors
        assert len(result.data["allTasks"]) == 1
        assert result.data["allTasks"][0]["title"] == "T1"

    def test_task(self):
        info = Mock()
        info.context.user = self.user
        result = schema.execute(f'{{ task(id: {self.task.id}) {{ id title }} }}', context=info.context)
        assert not result.errors
        assert result.data["task"]["title"] == "T1"

    def test_all_projects(self):
        info = Mock()
        info.context.user = self.user
        result = schema.execute("{ allProjects { id name taskCount } }", context=info.context)
        assert not result.errors
        assert len(result.data["allProjects"]) == 1
        assert result.data["allProjects"][0]["taskCount"] == 1

    def test_project(self):
        info = Mock()
        info.context.user = self.user
        result = schema.execute(f'{{ project(id: {self.project.id}) {{ id name }} }}', context=info.context)
        assert not result.errors
        assert result.data["project"]["name"] == "P1"

    def test_all_tags(self):
        info = Mock()
        info.context.user = self.user
        result = schema.execute("{ allTags { id name } }", context=info.context)
        assert not result.errors
        assert len(result.data["allTags"]) == 1
        assert result.data["allTags"][0]["name"] == "bug"

    def test_all_tasks_unauthenticated(self):
        info = Mock()
        info.context.user = None
        result = schema.execute("{ allTasks { id } }", context=info.context)
        assert result.errors is not None

    def test_all_tasks_filter_project(self):
        info = Mock()
        info.context.user = self.user
        other_project = Project.objects.create(owner=self.user, name="P2")
        Task.objects.create(owner=self.user, project=other_project, title="T2")
        result = schema.execute(f'{{ allTasks(projectId: {self.project.id}) {{ title }} }}', context=info.context)
        assert not result.errors
        assert len(result.data["allTasks"]) == 1
        assert result.data["allTasks"][0]["title"] == "T1"

    def test_all_tasks_filter_state(self):
        info = Mock()
        info.context.user = self.user
        Task.objects.create(owner=self.user, project=self.project, title="T2", state="done")
        result = schema.execute('{ allTasks(state: "done") { title } }', context=info.context)
        assert not result.errors
        assert len(result.data["allTasks"]) == 1
        assert result.data["allTasks"][0]["title"] == "T2"


@pytest.mark.django_db
class TestGraphQLMutations:
    @pytest.fixture(autouse=True)
    def setup_data(self, db):
        self.user = User.objects.create_user(username="h", email="h@h.com", password="pass")
        self.project = Project.objects.create(owner=self.user, name="P1")

    def test_create_task(self):
        info = Mock()
        info.context.user = self.user
        result = schema.execute(
            f'mutation {{ createTask(title: "New", projectId: {self.project.id}) {{ task {{ title }} }} }}',
            context=info.context,
        )
        assert not result.errors
        assert result.data["createTask"]["task"]["title"] == "New"
        assert Task.objects.filter(title="New", owner=self.user).exists()

    def test_create_task_invalid_project(self):
        info = Mock()
        info.context.user = self.user
        result = schema.execute(
            'mutation { createTask(title: "New", projectId: 999) { task { title } } }',
            context=info.context,
        )
        assert result.errors is not None

    def test_update_task(self):
        task = Task.objects.create(owner=self.user, project=self.project, title="Old")
        info = Mock()
        info.context.user = self.user
        result = schema.execute(
            f'mutation {{ updateTask(id: {task.id}, title: "Updated") {{ task {{ title }} }} }}',
            context=info.context,
        )
        assert not result.errors
        assert result.data["updateTask"]["task"]["title"] == "Updated"
        task.refresh_from_db()
        assert task.title == "Updated"

    def test_update_task_completed_sets_completed_at(self):
        """Paridad REST/GraphQL: completar vía mutation debe setear completed_at
        igual que el endpoint REST (antes quedaba NULL y rompía lead time)."""
        task = Task.objects.create(owner=self.user, project=self.project, title="Old")
        info = Mock()
        info.context.user = self.user
        result = schema.execute(
            f'mutation {{ updateTask(id: {task.id}, state: "completed") {{ task {{ state }} }} }}',
            context=info.context,
        )
        assert not result.errors
        task.refresh_from_db()
        assert task.state == "completed"
        assert task.completed_at is not None

    def test_update_task_reopen_clears_completed_at(self):
        task = Task.objects.create(
            owner=self.user, project=self.project, title="Old",
            state="completed", completed_at=timezone.now(),
        )
        info = Mock()
        info.context.user = self.user
        result = schema.execute(
            f'mutation {{ updateTask(id: {task.id}, state: "in_progress") {{ task {{ state }} }} }}',
            context=info.context,
        )
        assert not result.errors
        task.refresh_from_db()
        assert task.completed_at is None

    def test_update_task_invalid_state(self):
        task = Task.objects.create(owner=self.user, project=self.project, title="Old")
        info = Mock()
        info.context.user = self.user
        result = schema.execute(
            f'mutation {{ updateTask(id: {task.id}, state: "bogus") {{ task {{ state }} }} }}',
            context=info.context,
        )
        assert result.errors is not None
        task.refresh_from_db()
        assert task.state != "bogus"

    def test_update_task_not_found(self):
        info = Mock()
        info.context.user = self.user
        result = schema.execute(
            'mutation { updateTask(id: 999, title: "X") { task { title } } }',
            context=info.context,
        )
        assert result.errors is not None

    def test_delete_task(self):
        task = Task.objects.create(owner=self.user, project=self.project, title="Del")
        info = Mock()
        info.context.user = self.user
        result = schema.execute(
            f'mutation {{ deleteTask(id: {task.id}) {{ success }} }}',
            context=info.context,
        )
        assert not result.errors
        assert result.data["deleteTask"]["success"] is True
        assert not Task.objects.filter(id=task.id).exists()

    def test_delete_task_not_found(self):
        info = Mock()
        info.context.user = self.user
        result = schema.execute(
            'mutation { deleteTask(id: 999) { success } }',
            context=info.context,
        )
        assert result.errors is not None
