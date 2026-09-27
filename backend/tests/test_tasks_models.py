
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.projects.models import Project
from apps.tasks.models import (
    Epic,
    RecurrenceRule,
    Sprint,
    Task,
    TaskRelation,
    TaskTemplate,
)

User = get_user_model()


@pytest.mark.django_db
class TestTaskModel:
    @pytest.fixture(autouse=True)
    def setup_data(self, db):
        self.user = User.objects.create_user(username="tm", email="tm@tm.com", password="pass")
        self.project = Project.objects.create(owner=self.user, name="P1")

    def test_str(self):
        task = Task.objects.create(owner=self.user, title="T")
        assert str(task) == "T"

    def test_subtask_progress(self):
        task = Task.objects.create(owner=self.user, title="T")
        assert task.subtask_progress == (0, 0)
        Task.objects.create(owner=self.user, title="Sub1", parent=task, state="completed")
        Task.objects.create(owner=self.user, title="Sub2", parent=task, state="pending")
        assert task.subtask_progress == (1, 2)

    def test_generate_next_occurrence(self):
        recurrence = RecurrenceRule.objects.create(
            owner=self.user, frequency="daily", interval=1, count=5,
        )
        task = Task.objects.create(owner=self.user, title="T", recurrence=recurrence)
        new_task = task.generate_next_occurrence()
        assert new_task.title == task.title
        assert new_task.owner == task.owner
        assert new_task.recurrence == recurrence
        recurrence.refresh_from_db()
        assert recurrence.occurrences_generated == 1


@pytest.mark.django_db
class TestSprintModel:
    def test_str(self):
        user = User.objects.create_user(username="sm", email="sm@sm.com", password="pass")
        sprint = Sprint.objects.create(owner=user, name="S1", start_date=timezone.now().date(), end_date=timezone.now().date())
        assert str(sprint) == "S1"


@pytest.mark.django_db
class TestEpicModel:
    @pytest.fixture(autouse=True)
    def setup_data(self, db):
        self.user = User.objects.create_user(username="em", email="em@em.com", password="pass")
        self.project = Project.objects.create(owner=self.user, name="P1")

    def test_str(self):
        epic = Epic.objects.create(owner=self.user, title="E1", project=self.project)
        assert str(epic) == "E1"

    def test_progress(self):
        epic = Epic.objects.create(owner=self.user, title="E1", project=self.project)
        assert epic.progress == (0, 0)
        Task.objects.create(owner=self.user, title="T1", epic=epic, state="completed")
        Task.objects.create(owner=self.user, title="T2", epic=epic, state="pending")
        assert epic.progress == (1, 2)


@pytest.mark.django_db
class TestTaskTemplate:
    @pytest.fixture(autouse=True)
    def setup_data(self, db):
        self.user = User.objects.create_user(username="tt", email="tt@tt.com", password="pass")
        self.project = Project.objects.create(owner=self.user, name="P1")

    def test_str(self):
        template = TaskTemplate.objects.create(owner=self.user, name="Template")
        assert str(template) == "Template"

    def test_create_task(self):
        template = TaskTemplate.objects.create(
            owner=self.user, name="Template",
            template_data={"title": "T", "description": "D", "priority": 1, "state": "pending"},
            project=self.project,
        )
        task = template.create_task(self.user)
        assert task.title == "T"
        assert task.description == "D"
        assert task.priority == 1
        assert task.owner == self.user
        assert task.project == self.project

    def test_create_task_defaults(self):
        template = TaskTemplate.objects.create(owner=self.user, name="Template")
        task = template.create_task(self.user)
        assert task.title == "Template"
        assert task.priority == 3
        assert task.state == "pending"


@pytest.mark.django_db
class TestTaskRelation:
    def test_str(self):
        user = User.objects.create_user(username="tr", email="tr@tr.com", password="pass")
        t1 = Task.objects.create(owner=user, title="T1")
        t2 = Task.objects.create(owner=user, title="T2")
        rel = TaskRelation.objects.create(source=t1, target=t2, relation_type="blocks")
        assert str(t1.id) in str(rel)
        assert str(t2.id) in str(rel)
        assert "blocks" in str(rel)
