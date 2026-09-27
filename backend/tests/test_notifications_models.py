import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

from apps.notifications.models import Notification, NotificationPreference

User = get_user_model()


@pytest.mark.django_db
class TestNotification:
    @pytest.fixture(autouse=True)
    def setup_data(self, db):
        self.user = User.objects.create_user(username="nm", email="nm@nm.com", password="pass")

    def test_str(self):
        n = Notification.objects.create(recipient=self.user, title="Test", type="task_assigned")
        assert "nm" in str(n)
        assert "Test" in str(n)

    def test_choices(self):
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

    def test_defaults(self):
        n = Notification.objects.create(recipient=self.user, title="Test")
        assert n.type == "custom"
        assert n.read is False
        assert n.sent_in_app is True
        assert n.sent_email is False
        assert n.body == ""
        assert n.action_url == ""
        assert n.metadata == {}

    def test_ordering(self):
        n1 = Notification.objects.create(recipient=self.user, title="N1")
        n2 = Notification.objects.create(recipient=self.user, title="N2")
        from django.utils import timezone as _tz
        Notification.objects.filter(pk=n1.pk).update(created_at=_tz.now() - _tz.timedelta(hours=1))
        notifications = list(Notification.objects.all())
        assert notifications[0] == n2  # ordering by -created_at


@pytest.mark.django_db
class TestNotificationPreference:
    @pytest.fixture(autouse=True)
    def setup_data(self, db):
        self.user = User.objects.create_user(username="npm", email="npm@npm.com", password="pass")

    def test_str(self):
        p = NotificationPreference.objects.create(user=self.user, notification_type="task_assigned")
        assert "npm" in str(p)
        assert "task_assigned" in str(p)

    def test_defaults(self):
        p = NotificationPreference.objects.create(user=self.user, notification_type="task_assigned")
        assert p.in_app_enabled is True
        assert p.email_enabled is False
        assert p.digest_enabled is False

    def test_unique_together(self):
        NotificationPreference.objects.create(user=self.user, notification_type="task_assigned")
        with pytest.raises(IntegrityError):
            NotificationPreference.objects.create(user=self.user, notification_type="task_assigned")
