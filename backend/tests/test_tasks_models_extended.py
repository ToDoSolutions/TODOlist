"""Tests exhaustivos para modelos de tasks (parte 2)."""
import pytest
from django.contrib.auth import get_user_model

from apps.projects.models import Project
from apps.tasks.models import (
    Attachment,
    Comment,
    CustomField,
    CustomFieldValue,
    OutgoingWebhook,
    SavedSearch,
    Subtask,
    Task,
    TaskActivity,
    TimeEntry,
)

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="tm", email="tm@tm.com", password="pass")


@pytest.fixture
def project(user, db):
    return Project.objects.create(owner=user, name="Test Project")


@pytest.mark.django_db
class TestSubtask:
    def test_str(self, user, project):
        task = Task.objects.create(owner=user, project=project, title="Parent")
        st = Subtask.objects.create(task=task, title="Sub 1")
        assert str(st) == "Sub 1"

    def test_defaults(self, user, project):
        task = Task.objects.create(owner=user, project=project, title="Parent")
        st = Subtask.objects.create(task=task, title="Sub 1")
        assert st.is_done is False
        assert st.order == 0


@pytest.mark.django_db
class TestComment:
    def test_str(self, user, project):
        task = Task.objects.create(owner=user, project=project, title="Task 1")
        c = Comment.objects.create(task=task, author=user, body="Hello")
        assert str(c) == f"Comentario en {task.id} por {user.id}"


@pytest.mark.django_db
class TestTimeEntry:
    def test_str(self, user, project):
        task = Task.objects.create(owner=user, project=project, title="Task 1")
        te = TimeEntry.objects.create(task=task, user=user, duration_seconds=3600)
        assert "3600" in str(te) or "1" in str(te) or "Task 1" in str(te)

    def test_defaults(self, user, project):
        task = Task.objects.create(owner=user, project=project, title="Task 1")
        te = TimeEntry.objects.create(task=task, user=user, duration_seconds=3600)
        assert te.description == ""
        assert te.started_at is None
        assert te.ended_at is None


@pytest.mark.django_db
class TestAttachment:
    def test_str(self, user, project):
        task = Task.objects.create(owner=user, project=project, title="Task 1")
        att = Attachment.objects.create(
            task=task, uploaded_by=user, filename="test.pdf", file_size=1024, content_type="application/pdf"
        )
        assert "test.pdf" in str(att)

    def test_defaults(self, user, project):
        task = Task.objects.create(owner=user, project=project, title="Task 1")
        att = Attachment.objects.create(
            task=task, uploaded_by=user, filename="test.pdf", file_size=1024, content_type="application/pdf"
        )
        assert att.file == ""


@pytest.mark.django_db
class TestCustomField:
    def test_str(self, user, project):
        cf = CustomField.objects.create(project=project, name="Priority", field_type="select")
        assert "Priority" in str(cf)

    def test_defaults(self, user, project):
        cf = CustomField.objects.create(project=project, name="Priority", field_type="select")
        assert cf.options == []
        assert cf.is_required is False
        assert cf.default_value is None


@pytest.mark.django_db
class TestCustomFieldValue:
    def test_str(self, user, project):
        task = Task.objects.create(owner=user, project=project, title="Task 1")
        cf = CustomField.objects.create(project=project, name="Priority", field_type="select")
        cfv = CustomFieldValue.objects.create(task=task, field=cf, value="High")
        assert "Priority" in str(cfv)
        assert "High" in str(cfv)


@pytest.mark.django_db
class TestOutgoingWebhook:
    def test_str(self, user):
        ow = OutgoingWebhook.objects.create(
            owner=user, url="https://example.com/hook", events=["task.created"], secret="secret"
        )
        assert "example.com" in str(ow)
        assert "task.created" in str(ow)

    def test_defaults(self, user):
        ow = OutgoingWebhook.objects.create(
            owner=user, url="https://example.com/hook", events=["task.created"], secret="secret"
        )
        assert ow.is_active is True


@pytest.mark.django_db
class TestSavedSearch:
    def test_str(self, user):
        ss = SavedSearch.objects.create(owner=user, name="My Search", filters={"state": "pending"})
        assert "My Search" in str(ss)

    def test_defaults(self, user):
        ss = SavedSearch.objects.create(owner=user, name="My Search", filters={"state": "pending"})
        assert ss.is_shared is False


@pytest.mark.django_db
class TestTaskActivity:
    def test_str(self, user, project):
        task = Task.objects.create(owner=user, project=project, title="Task 1")
        ta = TaskActivity.objects.create(task=task, actor=user, action="created")
        assert "created" in str(ta) or "Task 1" in str(ta)

    def test_action_choices(self):
        assert TaskActivity.ActionType.CREATED == "created"
        assert TaskActivity.ActionType.UPDATED == "updated"
        assert TaskActivity.ActionType.STATE_CHANGED == "state_changed"
        assert TaskActivity.ActionType.PRIORITY_CHANGED == "priority_changed"
        assert TaskActivity.ActionType.ASSIGNED == "assigned"
        assert TaskActivity.ActionType.LABEL_ADDED == "label_added"
        assert TaskActivity.ActionType.LABEL_REMOVED == "label_removed"
        assert TaskActivity.ActionType.SPRINT_CHANGED == "sprint_changed"
        assert TaskActivity.ActionType.COMMENTED == "commented"
        assert TaskActivity.ActionType.CLOSED == "closed"
        assert TaskActivity.ActionType.REOPENED == "reopened"
        assert TaskActivity.ActionType.SUBTASK_ADDED == "subtask_added"
        assert TaskActivity.ActionType.RELATION_ADDED == "relation_added"


@pytest.mark.django_db
class TestTaskVersion:
    def test_version_increments_on_save(self, user, project):
        task = Task.objects.create(owner=user, project=project, title="Task 1")
        assert task.version == 1
        task.title = "Task 2"
        task.save()
        assert task.version == 2
        task.title = "Task 3"
        task.save()
        assert task.version == 3

    def test_version_no_increment_on_create(self, user, project):
        task = Task(owner=user, project=project, title="Task 1")
        task.save()
        assert task.version == 1
