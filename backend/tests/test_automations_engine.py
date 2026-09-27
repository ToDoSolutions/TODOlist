from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.automations.engine import (
    evaluate_conditions,
    execute_action,
    trigger_automation,
)
from apps.automations.models import AutomationLog, AutomationRule
from apps.notifications.models import Notification
from apps.tasks.models import Sprint, Task

User = get_user_model()


@pytest.mark.django_db
class TestEvaluateConditions:
    def test_equals_true(self):
        assert evaluate_conditions([{"field": "state", "operator": "equals", "value": "done"}], {"state": "done"}) is True

    def test_equals_false(self):
        assert evaluate_conditions([{"field": "state", "operator": "equals", "value": "done"}], {"state": "pending"}) is False

    def test_not_equals_true(self):
        assert evaluate_conditions([{"field": "state", "operator": "not_equals", "value": "done"}], {"state": "pending"}) is True

    def test_not_equals_false(self):
        assert evaluate_conditions([{"field": "state", "operator": "not_equals", "value": "done"}], {"state": "done"}) is False

    def test_contains_true(self):
        assert evaluate_conditions([{"field": "title", "operator": "contains", "value": "bug"}], {"title": "fix bug in login"}) is True

    def test_contains_false(self):
        assert evaluate_conditions([{"field": "title", "operator": "contains", "value": "bug"}], {"title": "add feature"}) is False

    def test_gt_true(self):
        assert evaluate_conditions([{"field": "priority", "operator": "gt", "value": 2}], {"priority": 5}) is True

    def test_gt_false(self):
        assert evaluate_conditions([{"field": "priority", "operator": "gt", "value": 2}], {"priority": 1}) is False

    def test_gt_invalid(self):
        assert evaluate_conditions([{"field": "priority", "operator": "gt", "value": 2}], {"priority": "abc"}) is False

    def test_lt_true(self):
        assert evaluate_conditions([{"field": "priority", "operator": "lt", "value": 3}], {"priority": 1}) is True

    def test_lt_false(self):
        assert evaluate_conditions([{"field": "priority", "operator": "lt", "value": 3}], {"priority": 5}) is False

    def test_unknown_operator_true(self):
        assert evaluate_conditions([{"field": "state", "operator": "unknown", "value": "done"}], {"state": "done"}) is True

    def test_empty_conditions_true(self):
        assert evaluate_conditions([], {"state": "done"}) is True

    def test_multiple_conditions(self):
        conds = [
            {"field": "state", "operator": "equals", "value": "done"},
            {"field": "priority", "operator": "gt", "value": 2},
        ]
        assert evaluate_conditions(conds, {"state": "done", "priority": 5}) is True
        assert evaluate_conditions(conds, {"state": "done", "priority": 1}) is False


@pytest.mark.django_db
class TestExecuteAction:
    @pytest.fixture(autouse=True)
    def setup_data(self, db):
        self.user = User.objects.create_user(username="a", email="a@a.com", password="pass")
        self.task = Task.objects.create(owner=self.user, title="Test", state="pending", priority=2)

    def test_set_priority(self):
        rule = AutomationRule.objects.create(owner=self.user, name="r1", trigger="task_created", action=AutomationRule.Action.SET_PRIORITY, action_params={"priority": 5})
        result = execute_action(rule, {"task": self.task})
        self.task.refresh_from_db()
        assert self.task.priority == 5
        assert result["old_priority"] == 2
        assert result["new_priority"] == 5

    def test_set_state(self):
        rule = AutomationRule.objects.create(owner=self.user, name="r2", trigger="task_created", action=AutomationRule.Action.SET_STATE, action_params={"state": "in_progress"})
        result = execute_action(rule, {"task": self.task})
        self.task.refresh_from_db()
        assert self.task.state == "in_progress"
        assert result["old_state"] == "pending"
        assert result["new_state"] == "in_progress"

    def test_set_due_date(self):
        rule = AutomationRule.objects.create(owner=self.user, name="r3", trigger="task_created", action=AutomationRule.Action.SET_DUE_DATE, action_params={"days_from_now": 10})
        result = execute_action(rule, {"task": self.task})
        self.task.refresh_from_db()
        assert "due_date" in result
        assert self.task.due_date is not None

    def test_move_to_sprint(self):
        sprint = Sprint.objects.create(owner=self.user, name="S1", state="active", start_date=timezone.now().date(), end_date=timezone.now().date() + timedelta(days=14))
        rule = AutomationRule.objects.create(owner=self.user, name="r4", trigger="task_created", action=AutomationRule.Action.MOVE_TO_SPRINT, action_params={"sprint_id": sprint.id})
        result = execute_action(rule, {"task": self.task})
        self.task.refresh_from_db()
        assert self.task.sprint == sprint
        assert result["new_sprint"] == "S1"

    def test_move_to_sprint_not_found(self):
        rule = AutomationRule.objects.create(owner=self.user, name="r4b", trigger="task_created", action=AutomationRule.Action.MOVE_TO_SPRINT, action_params={"sprint_id": 999})
        result = execute_action(rule, {"task": self.task})
        assert "error" in result
        assert "not found" in result["error"]

    def test_subtasks_in_progress(self):
        sub = Task.objects.create(owner=self.user, title="Sub", state="pending", parent=self.task)
        rule = AutomationRule.objects.create(owner=self.user, name="r5", trigger="task_created", action=AutomationRule.Action.SUBTASKS_IN_PROGRESS)
        result = execute_action(rule, {"task": self.task})
        sub.refresh_from_db()
        assert sub.state == "in_progress"
        assert result["moved_subtasks"] == 1

    def test_create_notification(self):
        rule = AutomationRule.objects.create(owner=self.user, name="r6", trigger="task_created", action=AutomationRule.Action.CREATE_NOTIFICATION, action_params={"title": "Auto"})
        result = execute_action(rule, {"task": self.task})
        assert result["notification_created"] is True
        assert Notification.objects.filter(recipient=self.user, title="Auto").exists()

    def test_create_task(self):
        rule = AutomationRule.objects.create(owner=self.user, name="r7", trigger="task_created", action=AutomationRule.Action.CREATE_TASK, action_params={"title": "New Task"})
        result = execute_action(rule, {"task": self.task})
        assert result["created_task_title"] == "New Task"
        assert Task.objects.filter(title="New Task", owner=self.user).exists()

    def test_set_assignee_by_id(self):
        assignee = User.objects.create_user(username="b", email="b@b.com", password="pass")
        rule = AutomationRule.objects.create(owner=self.user, name="r8", trigger="task_created", action=AutomationRule.Action.SET_ASSIGNEE, action_params={"assignee_id": assignee.id})
        result = execute_action(rule, {"task": self.task})
        self.task.refresh_from_db()
        assert self.task.assignee == assignee
        assert result["new_assignee"] == assignee.email

    def test_set_assignee_by_email(self):
        assignee = User.objects.create_user(username="c", email="c@c.com", password="pass")
        rule = AutomationRule.objects.create(owner=self.user, name="r9", trigger="task_created", action=AutomationRule.Action.SET_ASSIGNEE, action_params={"assignee_email": "c@c.com"})
        result = execute_action(rule, {"task": self.task})
        self.task.refresh_from_db()
        assert self.task.assignee == assignee
        assert result["new_assignee"] == "c@c.com"

    def test_add_tag(self):
        rule = AutomationRule.objects.create(owner=self.user, name="r10", trigger="task_created", action=AutomationRule.Action.ADD_TAG, action_params={"tag_name": "bug"})
        result = execute_action(rule, {"task": self.task})
        self.task.refresh_from_db()
        assert result["tag_added"] == "bug"
        assert result["tag_created"] is True
        assert self.task.tags.filter(name="bug").exists()

    def test_invalid_action(self):
        rule = AutomationRule.objects.create(owner=self.user, name="r11", trigger="task_created", action="invalid")
        result = execute_action(rule, {"task": self.task})
        assert "error" in result
        assert "not implemented" in result["error"]

    def test_no_task(self):
        rule = AutomationRule.objects.create(owner=self.user, name="r12", trigger="task_created", action=AutomationRule.Action.SET_PRIORITY, action_params={"priority": 5})
        result = execute_action(rule, {})
        assert "error" in result
        assert "requires a task in context" in result["error"]


@pytest.mark.django_db
class TestTriggerAutomation:
    @pytest.fixture(autouse=True)
    def setup_data(self, db):
        self.user = User.objects.create_user(username="d", email="d@d.com", password="pass")
        self.task = Task.objects.create(owner=self.user, title="Task", state="pending")

    def test_trigger_no_user(self):
        result = trigger_automation("task_created", {})
        assert result == []

    def test_trigger_user_from_task(self):
        AutomationRule.objects.create(owner=self.user, name="r1", trigger="task_created", action=AutomationRule.Action.SET_PRIORITY, action_params={"priority": 5})
        result = trigger_automation("task_created", {"task": self.task})
        assert len(result) == 1
        self.task.refresh_from_db()
        assert self.task.priority == 5

    def test_trigger_condition_skipped(self):
        AutomationRule.objects.create(owner=self.user, name="r2", trigger="task_created", action=AutomationRule.Action.SET_PRIORITY, action_params={"priority": 5}, conditions=[{"field": "state", "operator": "equals", "value": "done"}])
        result = trigger_automation("task_created", {"task": self.task})
        assert result == []
        assert AutomationLog.objects.filter(status=AutomationLog.Status.SKIPPED).exists()

    def test_trigger_success(self):
        AutomationRule.objects.create(owner=self.user, name="r3", trigger="task_created", action=AutomationRule.Action.SET_PRIORITY, action_params={"priority": 5})
        result = trigger_automation("task_created", {"task": self.task})
        assert len(result) == 1
        assert AutomationLog.objects.filter(status=AutomationLog.Status.SUCCESS).exists()
        self.task.refresh_from_db()
        assert self.task.priority == 5

    def test_trigger_disabled_rule(self):
        AutomationRule.objects.create(owner=self.user, name="r4", trigger="task_created", action=AutomationRule.Action.SET_PRIORITY, action_params={"priority": 5}, enabled=False)
        result = trigger_automation("task_created", {"task": self.task})
        assert result == []
        self.task.refresh_from_db()
        assert self.task.priority != 5

    def test_trigger_wrong_owner(self):
        other = User.objects.create_user(username="e", email="e@e.com", password="pass")
        AutomationRule.objects.create(owner=other, name="r5", trigger="task_created", action=AutomationRule.Action.SET_PRIORITY, action_params={"priority": 5})
        result = trigger_automation("task_created", {"task": self.task})
        assert result == []
        self.task.refresh_from_db()
        assert self.task.priority != 5
