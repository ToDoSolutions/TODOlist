"""Tests exhaustivos para modelos de automations."""
import pytest
from django.contrib.auth import get_user_model

from apps.automations.models import AutomationLog, AutomationRule

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="am", email="am@am.com", password="pass")


@pytest.mark.django_db
class TestAutomationRule:
    def test_str(self, user):
        rule = AutomationRule.objects.create(
            owner=user, name="Rule 1", trigger="task_created", action="set_priority"
        )
        assert "Rule 1" in str(rule)
        assert "task_created" in str(rule)
        assert "set_priority" in str(rule)

    def test_trigger_choices(self):
        assert AutomationRule.Trigger.TASK_CREATED == "task_created"
        assert AutomationRule.Trigger.TASK_STATE_CHANGED == "task_state_changed"
        assert AutomationRule.Trigger.TASK_COMPLETED == "task_completed"
        assert AutomationRule.Trigger.TASK_BLOCKED == "task_blocked"
        assert AutomationRule.Trigger.TASK_OVERDUE == "task_overdue"
        assert AutomationRule.Trigger.COMMENT_ADDED == "comment_added"
        assert AutomationRule.Trigger.SPRINT_STARTED == "sprint_started"
        assert AutomationRule.Trigger.SPRINT_CLOSED == "sprint_closed"
        assert AutomationRule.Trigger.DAILY_CHECK == "daily_check"

    def test_action_choices(self):
        assert AutomationRule.Action.SET_PRIORITY == "set_priority"
        assert AutomationRule.Action.SET_STATE == "set_state"
        assert AutomationRule.Action.SET_ASSIGNEE == "set_assignee"
        assert AutomationRule.Action.ADD_TAG == "add_tag"
        assert AutomationRule.Action.SET_DUE_DATE == "set_due_date"
        assert AutomationRule.Action.MOVE_TO_SPRINT == "move_to_sprint"
        assert AutomationRule.Action.SUBTASKS_IN_PROGRESS == "subtasks_in_progress"
        assert AutomationRule.Action.CREATE_NOTIFICATION == "create_notification"
        assert AutomationRule.Action.CREATE_TASK == "create_task"

    def test_condition_operator_choices(self):
        assert AutomationRule.ConditionOperator.EQUALS == "equals"
        assert AutomationRule.ConditionOperator.NOT_EQUALS == "not_equals"
        assert AutomationRule.ConditionOperator.CONTAINS == "contains"
        assert AutomationRule.ConditionOperator.GREATER_THAN == "gt"
        assert AutomationRule.ConditionOperator.LESS_THAN == "lt"

    def test_defaults(self, user):
        rule = AutomationRule.objects.create(
            owner=user, name="Rule 1", trigger="task_created", action="set_priority"
        )
        assert rule.enabled is True
        assert rule.description == ""
        assert rule.conditions == []
        assert rule.action_params == {}
        assert rule.trigger_count == 0
        assert rule.last_triggered_at is None

    def test_ordering(self, user):
        r1 = AutomationRule.objects.create(owner=user, name="Rule 1", trigger="task_created", action="set_priority")
        r2 = AutomationRule.objects.create(owner=user, name="Rule 2", trigger="task_created", action="set_priority")
        from django.utils import timezone as _tz
        AutomationRule.objects.filter(pk=r1.pk).update(created_at=_tz.now() - _tz.timedelta(hours=1))
        rules = list(AutomationRule.objects.all())
        assert rules[0] == r2  # ordering by -created_at


@pytest.mark.django_db
class TestAutomationLog:
    def test_str(self, user):
        rule = AutomationRule.objects.create(
            owner=user, name="Rule 1", trigger="task_created", action="set_priority"
        )
        log = AutomationLog.objects.create(rule=rule, status="success")
        assert "Rule 1" in str(log)
        assert "success" in str(log)

    def test_status_choices(self):
        assert AutomationLog.Status.SUCCESS == "success"
        assert AutomationLog.Status.FAILED == "failed"
        assert AutomationLog.Status.SKIPPED == "skipped"

    def test_defaults(self, user):
        rule = AutomationRule.objects.create(
            owner=user, name="Rule 1", trigger="task_created", action="set_priority"
        )
        log = AutomationLog.objects.create(rule=rule, status="success")
        assert log.trigger_data == {}
        assert log.action_result == {}
        assert log.error_message == ""

    def test_ordering(self, user):
        rule = AutomationRule.objects.create(
            owner=user, name="Rule 1", trigger="task_created", action="set_priority"
        )
        l1 = AutomationLog.objects.create(rule=rule, status="success")
        l2 = AutomationLog.objects.create(rule=rule, status="failed")
        from django.utils import timezone as _tz
        AutomationLog.objects.filter(pk=l1.pk).update(created_at=_tz.now() - _tz.timedelta(hours=1))
        logs = list(AutomationLog.objects.all())
        assert logs[0] == l2  # ordering by -created_at
