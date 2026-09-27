"""Tests exhaustivos para notifications/signals.py."""
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.notifications.models import Notification
from apps.projects.models import Project
from apps.tasks.models import Comment, Sprint, Task

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="ns", email="ns@ns.com", password="pass")


@pytest.fixture
def other_user(db):
    return User.objects.create_user(username="ns2", email="ns2@ns.com", password="pass")


@pytest.fixture
def project(user, db):
    return Project.objects.create(owner=user, name="Test Project")


@pytest.mark.django_db
class TestNotifyOnComment:
    def test_notifies_owner(self, user, other_user, project):
        """Verifica que el owner recibe notificación cuando otro comenta."""
        task = Task.objects.create(owner=user, project=project, title="Task")
        Comment.objects.create(task=task, author=other_user, body="Hello")
        assert Notification.objects.filter(
            recipient=user, type="task_commented"
        ).exists()

    def test_no_self_notify(self, user, project):
        """Verifica que el owner no se notifica a sí mismo."""
        task = Task.objects.create(owner=user, project=project, title="Task")
        Comment.objects.create(task=task, author=user, body="Hello")
        assert not Notification.objects.filter(
            recipient=user, type="task_commented"
        ).exists()

    def test_no_notify_on_update(self, user, other_user, project):
        """Verifica que no notifica en actualización de comentario."""
        task = Task.objects.create(owner=user, project=project, title="Task")
        comment = Comment.objects.create(task=task, author=other_user, body="Hello")
        Notification.objects.all().delete()
        comment.body = "Updated"
        comment.save()
        assert not Notification.objects.filter(type="task_commented").exists()


@pytest.mark.django_db
class TestNotifyOnTaskAssigned:
    def test_notifies_assignee(self, user, other_user, project):
        """Verifica que el assignee recibe notificación."""
        Task.objects.create(
            owner=user, project=project, title="Task", assignee=other_user
        )
        assert Notification.objects.filter(
            recipient=other_user, type="task_assigned"
        ).exists()

    def test_no_notify_owner_assignee(self, user, project):
        """Verifica que no notifica si assignee == owner."""
        Task.objects.create(owner=user, project=project, title="Task", assignee=user)
        assert not Notification.objects.filter(type="task_assigned").exists()

    def test_no_notify_no_assignee(self, user, project):
        """Verifica que no notifica si no hay assignee."""
        Task.objects.create(owner=user, project=project, title="Task")
        assert not Notification.objects.filter(type="task_assigned").exists()


@pytest.mark.django_db
class TestNotifyOnSprintStateChange:
    def test_notifies_on_active(self, user, project):
        """Verifica que notifica cuando sprint pasa a active."""
        sprint = Sprint.objects.create(
            owner=user, project=project, name="Sprint 1",
            start_date=timezone.now().date(), end_date=timezone.now().date() + timedelta(days=14)
        )
        sprint.state = "active"
        sprint.save()
        assert Notification.objects.filter(
            recipient=user, type="sprint_started"
        ).exists()

    def test_notifies_on_closed(self, user, project):
        """Verifica que notifica cuando sprint pasa a closed."""
        sprint = Sprint.objects.create(
            owner=user, project=project, name="Sprint 1",
            start_date=timezone.now().date(), end_date=timezone.now().date() + timedelta(days=14)
        )
        sprint.state = "closed"
        sprint.save()
        assert Notification.objects.filter(
            recipient=user, type="sprint_closed"
        ).exists()

    def test_no_notify_on_create(self, user, project):
        """Verifica que no notifica en creación."""
        Sprint.objects.create(
            owner=user, project=project, name="Sprint 1",
            start_date=timezone.now().date(), end_date=timezone.now().date() + timedelta(days=14)
        )
        assert not Notification.objects.filter(type="sprint_started").exists()
