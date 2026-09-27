"""Tests exhaustivos para automations/signals.py y tasks.py."""
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.automations.models import AutomationLog, AutomationRule
from apps.projects.models import Project
from apps.tasks.models import Comment, Sprint, Task

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="as", email="as@as.com", password="pass")


@pytest.fixture
def project(user, db):
    return Project.objects.create(owner=user, name="Test Project")


@pytest.mark.django_db
class TestTaskAutomationSignals:
    def test_task_created_trigger(self, user, project):
        """Verifica que crear tarea dispara TASK_CREATED."""
        AutomationRule.objects.create(
            owner=user, name="Rule", trigger="task_created", action="set_priority",
            action_params={"priority": 0}
        )
        task = Task.objects.create(owner=user, project=project, title="Task")
        assert AutomationLog.objects.filter(status="success").exists()
        task.refresh_from_db()
        assert task.priority == 0

    def test_state_changed_trigger(self, user, project):
        """Verifica que cambiar estado dispara TASK_STATE_CHANGED."""
        AutomationRule.objects.create(
            owner=user, name="Rule", trigger="task_state_changed", action="create_notification",
            action_params={"title": "Changed"}
        )
        task = Task.objects.create(owner=user, project=project, title="Task", state="pending")
        task.state = "in_progress"
        task.save()
        assert AutomationLog.objects.filter(status="success").exists()

    def test_completed_trigger(self, user, project):
        """Verifica que pasar a completed dispara TASK_COMPLETED."""
        AutomationRule.objects.create(
            owner=user, name="Rule", trigger="task_completed", action="create_notification",
            action_params={"title": "Done"}
        )
        task = Task.objects.create(owner=user, project=project, title="Task", state="pending")
        task.state = "completed"
        task.save()
        assert AutomationLog.objects.filter(status="success").exists()

    def test_blocked_trigger(self, user, project):
        """Verifica que pasar a blocked dispara TASK_BLOCKED."""
        AutomationRule.objects.create(
            owner=user, name="Rule", trigger="task_blocked", action="create_notification",
            action_params={"title": "Blocked"}
        )
        task = Task.objects.create(owner=user, project=project, title="Task", state="pending")
        task.state = "blocked"
        task.save()
        assert AutomationLog.objects.filter(status="success").exists()


@pytest.mark.django_db
class TestCommentAutomationSignal:
    def test_comment_added_trigger(self, user, project):
        """Verifica que crear comentario dispara COMMENT_ADDED."""
        AutomationRule.objects.create(
            owner=user, name="Rule", trigger="comment_added", action="create_notification",
            action_params={"title": "Comment"}
        )
        task = Task.objects.create(owner=user, project=project, title="Task")
        Comment.objects.create(task=task, author=user, body="Hello")
        assert AutomationLog.objects.filter(status="success").exists()


@pytest.mark.django_db
class TestSprintAutomationSignal:
    def test_sprint_started_trigger(self, user, project):
        """Verifica que activar sprint dispara SPRINT_STARTED."""
        AutomationRule.objects.create(
            owner=user, name="Rule", trigger="sprint_started", action="create_notification",
            action_params={"title": "Sprint"}
        )
        sprint = Sprint.objects.create(
            owner=user, project=project, name="Sprint",
            start_date=timezone.now().date(), end_date=timezone.now().date() + timedelta(days=14)
        )
        sprint.state = "active"
        sprint.save()
        assert AutomationLog.objects.filter(status="success").exists()

    def test_sprint_closed_trigger(self, user, project):
        """Verifica que cerrar sprint dispara SPRINT_CLOSED."""
        AutomationRule.objects.create(
            owner=user, name="Rule", trigger="sprint_closed", action="create_notification",
            action_params={"title": "Closed"}
        )
        sprint = Sprint.objects.create(
            owner=user, project=project, name="Sprint",
            start_date=timezone.now().date(), end_date=timezone.now().date() + timedelta(days=14)
        )
        sprint.state = "closed"
        sprint.save()
        assert AutomationLog.objects.filter(status="success").exists()


@pytest.mark.django_db
class TestRunDailyChecksTask:
    def test_run_daily_checks_task(self):
        """Verifica que la tarea de Celery ejecuta run_daily_checks."""
        from apps.automations.tasks import run_daily_checks_task
        with patch("apps.automations.engine.run_daily_checks", return_value=[{"rule": "test"}]):
            result = run_daily_checks_task()
            assert "1 actions" in result
