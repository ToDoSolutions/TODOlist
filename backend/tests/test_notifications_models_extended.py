"""Tests exhaustivos para modelos de notifications."""
import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

from apps.notifications.models import Notification, NotificationPreference
from apps.projects.models import Project
from apps.tasks.models import Task

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="nm", email="nm@nm.com", password="pass")


@pytest.fixture
def project(user, db):
    return Project.objects.create(owner=user, name="Test Project")


@pytest.mark.django_db
class TestNotification:
    def test_str(self, user):
        n = Notification.objects.create(recipient=user, title="Test", type="task_assigned")
        assert user.username in str(n)
        assert "Test" in str(n)

    def test_type_choices(self):
        assert Notification.Type.TASK_ASSIGNED == "task_assigned"
        assert Notification.Type.TASK_DUE_SOON == "task_due_soon"
        assert Notification.Type.TASK_OVERDUE == "task_overdue"
        assert Notification.Type.TASK_COMPLETED == "task_completed"
        assert Notification.Type.TASK_COMMENTED == "task_commented"
        assert Notification.Type.TASK_BLOCKED == "task_blocked"
        assert Notification.Type.SPRINT_STARTED == "sprint_started"
        assert Notification.Type.SPRINT_ENDING == "sprint_ending"
        assert Notification.Type.SPRINT_CLOSED == "sprint_closed"
        assert Notification.Type.MENTION == "mention"
        assert Notification.Type.PR_OPENED == "pr_opened"
        assert Notification.Type.PR_MERGED == "pr_merged"
        assert Notification.Type.PR_REVIEW_REQUESTED == "pr_review_requested"
        assert Notification.Type.CI_FAILED == "ci_failed"
        assert Notification.Type.RELEASE_PUBLISHED == "release_published"
        assert Notification.Type.AUTOMATION_TRIGGERED == "automation_triggered"
        assert Notification.Type.CUSTOM == "custom"

    def test_defaults(self, user):
        n = Notification.objects.create(recipient=user, title="Test", type="task_assigned")
        assert n.body == ""
        assert n.task is None
        assert n.sprint is None
        assert n.action_url == ""
        assert n.metadata == {}
        assert n.read is False
        assert n.read_at is None
        assert n.sent_in_app is True
        assert n.sent_email is False

    def test_ordering(self, user):
        n1 = Notification.objects.create(recipient=user, title="N1", type="task_assigned")
        n2 = Notification.objects.create(recipient=user, title="N2", type="task_assigned")
        from django.utils import timezone as _tz
        Notification.objects.filter(pk=n1.pk).update(created_at=_tz.now() - _tz.timedelta(hours=1))
        notifications = list(Notification.objects.all())
        assert notifications[0] == n2  # ordering by -created_at

    def test_task_relation(self, user, project):
        task = Task.objects.create(owner=user, project=project, title="Task 1")
        n = Notification.objects.create(recipient=user, title="Test", type="task_assigned", task=task)
        assert n.task == task
        assert task.notifications.count() == 1


@pytest.mark.django_db
class TestNotificationPreference:
    def test_str(self, user):
        np = NotificationPreference.objects.create(user=user, notification_type="task_assigned")
        assert user.username in str(np)
        assert "task_assigned" in str(np)

    def test_defaults(self, user):
        np = NotificationPreference.objects.create(user=user, notification_type="task_assigned")
        assert np.in_app_enabled is True
        assert np.email_enabled is False
        assert np.digest_enabled is False

    def test_unique_together(self, user):
        NotificationPreference.objects.create(user=user, notification_type="task_assigned")
        with pytest.raises(IntegrityError):
            NotificationPreference.objects.create(user=user, notification_type="task_assigned")
