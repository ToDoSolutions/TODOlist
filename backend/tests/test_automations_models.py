import pytest
from django.contrib.auth import get_user_model

from apps.automations.models import AutomationLog, AutomationRule

User = get_user_model()


@pytest.mark.django_db
class TestAutomationRule:
    @pytest.fixture(autouse=True)
    def setup_data(self, db):
        self.user = User.objects.create_user(username="arm", email="arm@arm.com", password="pass")

    def test_str(self):
        rule = AutomationRule.objects.create(owner=self.user, name="R1", trigger="task_created", action="set_priority")
        assert "R1" in str(rule)
        assert "task_created" in str(rule)
        assert "set_priority" in str(rule)

    def test_choices(self):
        assert AutomationRule.Trigger.TASK_CREATED == "task_created"
        assert AutomationRule.Trigger.TASK_STATE_CHANGED == "task_state_changed"
        assert AutomationRule.Trigger.TASK_COMPLETED == "task_completed"
        assert AutomationRule.Trigger.TASK_BLOCKED == "task_blocked"
        assert AutomationRule.Trigger.TASK_OVERDUE == "task_overdue"
        assert AutomationRule.Trigger.COMMENT_ADDED == "comment_added"
        assert AutomationRule.Trigger.SPRINT_STARTED == "sprint_started"
        assert AutomationRule.Trigger.SPRINT_CLOSED == "sprint_closed"
        assert AutomationRule.Trigger.DAILY_CHECK == "daily_check"

        assert AutomationRule.Action.SET_PRIORITY == "set_priority"
        assert AutomationRule.Action.SET_STATE == "set_state"
        assert AutomationRule.Action.SET_ASSIGNEE == "set_assignee"
        assert AutomationRule.Action.ADD_TAG == "add_tag"
        assert AutomationRule.Action.SET_DUE_DATE == "set_due_date"
        assert AutomationRule.Action.MOVE_TO_SPRINT == "move_to_sprint"
        assert AutomationRule.Action.SUBTASKS_IN_PROGRESS == "subtasks_in_progress"
        assert AutomationRule.Action.CREATE_NOTIFICATION == "create_notification"
        assert AutomationRule.Action.CREATE_TASK == "create_task"

        assert AutomationRule.ConditionOperator.EQUALS == "equals"
        assert AutomationRule.ConditionOperator.NOT_EQUALS == "not_equals"
        assert AutomationRule.ConditionOperator.CONTAINS == "contains"
        assert AutomationRule.ConditionOperator.GREATER_THAN == "gt"
        assert AutomationRule.ConditionOperator.LESS_THAN == "lt"

    def test_defaults(self):
        rule = AutomationRule.objects.create(owner=self.user, name="R1", trigger="task_created", action="set_priority")
        assert rule.enabled is True
        assert rule.conditions == []
        assert rule.action_params == {}
        assert rule.trigger_count == 0
        assert rule.description == ""

    def test_ordering(self):
        r1 = AutomationRule.objects.create(owner=self.user, name="R1", trigger="task_created", action="set_priority")
        r2 = AutomationRule.objects.create(owner=self.user, name="R2", trigger="task_completed", action="set_state")
        # auto_now_add puede asignar el mismo timestamp en SQLite: fijar explícito
        from django.utils import timezone as tz
        AutomationRule.objects.filter(pk=r1.pk).update(created_at=tz.now() - tz.timedelta(hours=2))
        AutomationRule.objects.filter(pk=r2.pk).update(created_at=tz.now() - tz.timedelta(hours=1))
        rules = list(AutomationRule.objects.all())
        assert rules[0] == r2  # ordering by -created_at


@pytest.mark.django_db
class TestAutomationLog:
    @pytest.fixture(autouse=True)
    def setup_data(self, db):
        self.user = User.objects.create_user(username="alm", email="alm@alm.com", password="pass")
        self.rule = AutomationRule.objects.create(owner=self.user, name="R1", trigger="task_created", action="set_priority")

    def test_str(self):
        log = AutomationLog.objects.create(rule=self.rule, status="success", trigger_data={}, action_result={})
        assert "R1" in str(log)
        assert "success" in str(log)

    def test_choices(self):
        assert AutomationLog.Status.SUCCESS == "success"
        assert AutomationLog.Status.FAILED == "failed"
        assert AutomationLog.Status.SKIPPED == "skipped"

    def test_defaults(self):
        log = AutomationLog.objects.create(rule=self.rule, status="success")
        assert log.trigger_data == {}
        assert log.action_result == {}
        assert log.error_message == ""
