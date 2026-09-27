"""Tests exhaustivos para automations/engine.py."""

import pytest
from django.contrib.auth import get_user_model

from apps.automations.engine import (
    evaluate_conditions,
    execute_action,
    trigger_automation,
)
from apps.automations.models import AutomationLog, AutomationRule
from apps.projects.models import Project
from apps.tasks.models import Task

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="ae", email="ae@ae.com", password="pass")


@pytest.fixture
def project(user, db):
    return Project.objects.create(owner=user, name="Test Project")


@pytest.mark.django_db
class TestEvaluateConditions:
    def test_empty_conditions(self):
        assert evaluate_conditions([], {}) is True

    def test_equals(self):
        conditions = [{"field": "state", "operator": "equals", "value": "pending"}]
        assert evaluate_conditions(conditions, {"state": "pending"}) is True
        assert evaluate_conditions(conditions, {"state": "done"}) is False

    def test_not_equals(self):
        conditions = [{"field": "state", "operator": "not_equals", "value": "pending"}]
        assert evaluate_conditions(conditions, {"state": "done"}) is True
        assert evaluate_conditions(conditions, {"state": "pending"}) is False

    def test_contains(self):
        conditions = [{"field": "title", "operator": "contains", "value": "bug"}]
        assert evaluate_conditions(conditions, {"title": "Fix bug"}) is True
        assert evaluate_conditions(conditions, {"title": "Fix feature"}) is False

    def test_gt(self):
        conditions = [{"field": "priority", "operator": "gt", "value": 3}]
        assert evaluate_conditions(conditions, {"priority": 5}) is True
        assert evaluate_conditions(conditions, {"priority": 2}) is False

    def test_lt(self):
        conditions = [{"field": "priority", "operator": "lt", "value": 3}]
        assert evaluate_conditions(conditions, {"priority": 2}) is True
        assert evaluate_conditions(conditions, {"priority": 5}) is False

    def test_gt_invalid(self):
        conditions = [{"field": "priority", "operator": "gt", "value": "abc"}]
        assert evaluate_conditions(conditions, {"priority": 5}) is False

    def test_multiple_conditions(self):
        conditions = [
            {"field": "state", "operator": "equals", "value": "pending"},
            {"field": "priority", "operator": "gt", "value": 2},
        ]
        assert evaluate_conditions(conditions, {"state": "pending", "priority": 3}) is True
        assert evaluate_conditions(conditions, {"state": "pending", "priority": 1}) is False


@pytest.mark.django_db
class TestExecuteAction:
    def test_set_priority(self, user, project):
        task = Task.objects.create(owner=user, project=project, title="Task", priority=3)
        rule = AutomationRule.objects.create(
            owner=user, name="Rule", trigger="task_created", action="set_priority",
            action_params={"priority": 0}
        )
        result = execute_action(rule, {"task": task})
        task.refresh_from_db()
        assert task.priority == 0
        assert result["old_priority"] == 3
        assert result["new_priority"] == 0

    def test_set_state(self, user, project):
        task = Task.objects.create(owner=user, project=project, title="Task", state="pending")
        rule = AutomationRule.objects.create(
            owner=user, name="Rule", trigger="task_created", action="set_state",
            action_params={"state": "in_progress"}
        )
        result = execute_action(rule, {"task": task})
        task.refresh_from_db()
        assert task.state == "in_progress"
        assert result["old_state"] == "pending"
        assert result["new_state"] == "in_progress"

    def test_set_due_date(self, user, project):
        task = Task.objects.create(owner=user, project=project, title="Task")
        rule = AutomationRule.objects.create(
            owner=user, name="Rule", trigger="task_created", action="set_due_date",
            action_params={"days_from_now": 7}
        )
        result = execute_action(rule, {"task": task})
        task.refresh_from_db()
        assert task.due_date is not None
        assert "due_date" in result

    def test_create_notification(self, user, project):
        rule = AutomationRule.objects.create(
            owner=user, name="Rule", trigger="task_created", action="create_notification",
            action_params={"title": "Test", "body": "Test body"}
        )
        result = execute_action(rule, {"task": None})
        assert result["notification_created"] is True

    def test_create_task(self, user, project):
        rule = AutomationRule.objects.create(
            owner=user, name="Rule", trigger="task_created", action="create_task",
            action_params={"title": "New Task", "description": "Desc", "priority": 1}
        )
        result = execute_action(rule, {"task": None})
        assert "created_task_id" in result
        assert Task.objects.filter(title="New Task").exists()


@pytest.mark.django_db
class TestTriggerAutomation:
    def test_trigger_automation(self, user, project):
        AutomationRule.objects.create(
            owner=user, name="Rule", trigger="task_created", action="set_priority",
            action_params={"priority": 0}
        )
        task = Task.objects.create(owner=user, project=project, title="Task")
        results = trigger_automation("task_created", {"task": task, "user": user})
        assert len(results) == 1
        assert results[0]["rule"] == "Rule"
        assert "result" in results[0]

    def test_trigger_automation_disabled(self, user, project):
        AutomationRule.objects.create(
            owner=user, name="Rule", trigger="task_created", action="set_priority",
            enabled=False
        )
        task = Task.objects.create(owner=user, project=project, title="Task")
        results = trigger_automation("task_created", {"task": task, "user": user})
        assert len(results) == 0

    def test_trigger_automation_condition_fails(self, user, project):
        rule = AutomationRule.objects.create(
            owner=user, name="Rule", trigger="task_created", action="set_priority",
            conditions=[{"field": "priority", "operator": "equals", "value": 0}],
            action_params={"priority": 0}
        )
        task = Task.objects.create(owner=user, project=project, title="Task", priority=3)
        results = trigger_automation("task_created", {"task": task, "user": user})
        # Condición falla → no se añade a results, pero se crea AutomationLog con SKIPPED
        assert len(results) == 0
        assert AutomationLog.objects.filter(rule=rule, status="skipped").exists()
