from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model

from apps.notifications.models import Notification, NotificationPreference
from apps.notifications.services import (
    get_unread_count,
    mark_all_as_read,
    mark_as_read,
    notify,
)
from apps.tasks.models import Task

User = get_user_model()


@pytest.mark.django_db
class TestNotify:
    @pytest.fixture(autouse=True)
    def setup_data(self, db):
        self.user = User.objects.create_user(username="n1", email="n1@n.com", password="pass")

    def test_notify_in_app(self):
        notif = notify(self.user, "test", "Title", "Body")
        assert notif.title == "Title"
        assert notif.body == "Body"
        assert notif.sent_in_app is True
        assert notif.sent_email is False

    def test_notify_with_task(self):
        task = Task.objects.create(owner=self.user, title="T")
        notif = notify(self.user, "test", "Title", task=task)
        assert notif.task == task

    def test_notify_disabled(self):
        NotificationPreference.objects.create(user=self.user, notification_type="test", in_app_enabled=False, email_enabled=False)
        notif = notify(self.user, "test", "Title")
        assert notif is None
        assert not Notification.objects.filter(recipient=self.user).exists()

    def test_notify_email_only(self, settings):
        # Email opt-in doble: pref del usuario + flag global del servidor,
        # y solo para tipos elegibles (task_assigned/mention/reminder).
        settings.EMAIL_NOTIFICATIONS_ENABLED = True
        NotificationPreference.objects.create(user=self.user, notification_type="task_assigned", in_app_enabled=False, email_enabled=True)
        with patch("apps.notifications.services._send_email_notification", return_value=True) as mock_email:
            notif = notify(self.user, "task_assigned", "Title")
            assert notif is None
            mock_email.assert_called_once()

    def test_notify_both(self, settings):
        settings.EMAIL_NOTIFICATIONS_ENABLED = True
        NotificationPreference.objects.create(user=self.user, notification_type="task_assigned", in_app_enabled=True, email_enabled=True)
        with patch("apps.notifications.services._send_email_notification", return_value=True):
            notif = notify(self.user, "task_assigned", "Title")
            assert notif is not None
            assert notif.sent_email is True

    def test_notify_metadata(self):
        notif = notify(self.user, "test", "Title", metadata={"key": "value"})
        assert notif.metadata == {"key": "value"}


@pytest.mark.django_db
class TestMarkAsRead:
    @pytest.fixture(autouse=True)
    def setup_data(self, db):
        self.user = User.objects.create_user(username="n2", email="n2@n.com", password="pass")
        self.notif = Notification.objects.create(recipient=self.user, type="test", title="T")

    def test_mark_as_read(self):
        result = mark_as_read(self.notif.id, self.user)
        assert result.read is True
        assert result.read_at is not None

    def test_mark_as_read_not_found(self):
        assert mark_as_read(999, self.user) is None

    def test_mark_as_read_wrong_user(self):
        other = User.objects.create_user(username="n3", email="n3@n.com", password="pass")
        assert mark_as_read(self.notif.id, other) is None

    def test_mark_all_as_read(self):
        Notification.objects.create(recipient=self.user, type="test", title="T2")
        Notification.objects.create(recipient=self.user, type="test", title="T3")
        count = mark_all_as_read(self.user)
        assert count == 3
        assert Notification.objects.filter(recipient=self.user, read=True).count() == 3

    def test_get_unread_count(self):
        Notification.objects.create(recipient=self.user, type="test", title="T2", read=True)
        assert get_unread_count(self.user) == 1
        mark_all_as_read(self.user)
        assert get_unread_count(self.user) == 0
