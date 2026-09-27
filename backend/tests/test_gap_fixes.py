"""Tests para los 3 gaps arreglados: WebhookDelivery filtering, SET_ASSIGNEE, ADD_TAG,
TASK_COMPLETED/TASK_BLOCKED/SPRINT_STARTED triggers."""

import pytest
from django.contrib.auth import get_user_model

from apps.automations.engine import execute_action
from apps.automations.models import AutomationLog, AutomationRule
from apps.integrations.models import GitHubInstallation, GitHubRepo, WebhookDelivery
from apps.tags.models import Tag
from apps.tasks.models import Sprint, Task

User = get_user_model()


# --- WebhookDelivery filtering ---

@pytest.mark.django_db
class TestWebhookDeliveryUserFilter:
    def test_usuario_sin_repos_no_ve_entregas(self, authed_client):
        """Usuario sin instalaciones de GitHub no ve ninguna entrega."""
        WebhookDelivery.objects.create(
            delivery_id="del-x",
            event_type="issues",
            action="opened",
            payload={},
            status="processed",
            repo_full_name="someoneelse/repo",
        )
        resp = authed_client.get("/api/webhooks/deliveries/")
        assert resp.status_code == 200
        assert len(resp.data) == 0

    def test_usuario_ve_solo_sus_entregas(self, authed_client, user):
        """Usuario ve solo entregas de sus repos."""
        inst = GitHubInstallation.objects.create(
            user=user, installation_id=100, account_login="me", account_type="User",
        )
        GitHubRepo.objects.create(
            installation=inst, repo_id=1, full_name="me/myrepo",
            name="myrepo", owner="me",
        )
        WebhookDelivery.objects.create(
            delivery_id="del-mine", event_type="issues", action="opened",
            payload={}, status="processed", repo_full_name="me/myrepo",
        )
        WebhookDelivery.objects.create(
            delivery_id="del-not-mine", event_type="issues", action="opened",
            payload={}, status="processed", repo_full_name="other/repo",
        )
        resp = authed_client.get("/api/webhooks/deliveries/")
        assert resp.status_code == 200
        assert len(resp.data) == 1
        assert resp.data[0]["delivery_id"] == "del-mine"


# --- SET_ASSIGNEE ---

@pytest.mark.django_db
class TestSetAssigneeAction:
    def test_set_assignee_by_email(self, user, task):
        """SET_ASSIGNEE asigna un usuario por email."""
        from apps.collaboration.models import ProjectMember
        assignee = User.objects.create_user(
            email="assignee@test.com", username="assignee", password="pass123",
        )
        ProjectMember.objects.create(project=task.project, user=assignee)
        rule = AutomationRule.objects.create(
            owner=user,
            name="Assign on create",
            trigger=AutomationRule.Trigger.TASK_CREATED,
            action=AutomationRule.Action.SET_ASSIGNEE,
            action_params={"assignee_email": "assignee@test.com"},
            enabled=True,
        )
        result = execute_action(rule, {"task": task, "user": user})
        assert "new_assignee" in result
        assert result["new_assignee"] == "assignee@test.com"
        task.refresh_from_db()
        assert task.assignee == assignee

    def test_set_assignee_nonexistent_user(self, user, task):
        """SET_ASSIGNEE con email inexistente devuelve error."""
        rule = AutomationRule.objects.create(
            owner=user,
            name="Assign nonexistent",
            trigger=AutomationRule.Trigger.TASK_CREATED,
            action=AutomationRule.Action.SET_ASSIGNEE,
            action_params={"assignee_email": "ghost@test.com"},
            enabled=True,
        )
        result = execute_action(rule, {"task": task, "user": user})
        assert "error" in result
        assert "ghost@test.com" in result["error"]


# --- ADD_TAG ---

@pytest.mark.django_db
class TestAddTagAction:
    def test_add_tag_creates_new_tag(self, user, task):
        """ADD_TAG crea una etiqueta nueva y la añade a la tarea."""
        rule = AutomationRule.objects.create(
            owner=user,
            name="Tag on create",
            trigger=AutomationRule.Trigger.TASK_CREATED,
            action=AutomationRule.Action.ADD_TAG,
            action_params={"tag_name": "automated", "tag_color": "#ff0000"},
            enabled=True,
        )
        result = execute_action(rule, {"task": task, "user": user})
        assert result["tag_added"] == "automated"
        assert result["tag_created"] is True
        assert task.tags.filter(name="automated").exists()

    def test_add_tag_reuses_existing_tag(self, user, task):
        """ADD_TAG reutiliza una etiqueta existente."""
        Tag.objects.create(name="existing", owner=user, color="#00ff00")
        rule = AutomationRule.objects.create(
            owner=user,
            name="Tag existing",
            trigger=AutomationRule.Trigger.TASK_CREATED,
            action=AutomationRule.Action.ADD_TAG,
            action_params={"tag_name": "existing"},
            enabled=True,
        )
        result = execute_action(rule, {"task": task, "user": user})
        assert result["tag_created"] is False
        assert task.tags.filter(name="existing").exists()


# --- TASK_COMPLETED / TASK_BLOCKED triggers ---

@pytest.mark.django_db
class TestTaskStateTriggers:
    def test_task_completed_triggers_automation(self, user, task):
        """Cambiar estado a completed dispara TASK_COMPLETED."""
        AutomationRule.objects.create(
            owner=user,
            name="On complete",
            trigger=AutomationRule.Trigger.TASK_COMPLETED,
            action=AutomationRule.Action.CREATE_NOTIFICATION,
            action_params={"title": "Task completed!"},
            enabled=True,
        )
        task.state = Task.State.COMPLETED
        task.save()
        logs = AutomationLog.objects.filter(
            rule__trigger=AutomationRule.Trigger.TASK_COMPLETED
        )
        assert logs.exists()
        assert logs.first().status == AutomationLog.Status.SUCCESS

    def test_task_blocked_triggers_automation(self, user, task):
        """Cambiar estado a blocked dispara TASK_BLOCKED."""
        AutomationRule.objects.create(
            owner=user,
            name="On blocked",
            trigger=AutomationRule.Trigger.TASK_BLOCKED,
            action=AutomationRule.Action.CREATE_NOTIFICATION,
            action_params={"title": "Task blocked!"},
            enabled=True,
        )
        task.state = Task.State.BLOCKED
        task.save()
        logs = AutomationLog.objects.filter(
            rule__trigger=AutomationRule.Trigger.TASK_BLOCKED
        )
        assert logs.exists()
        assert logs.first().status == AutomationLog.Status.SUCCESS

    def test_task_state_change_does_not_trigger_completed(self, user, task):
        """Cambiar a in_progress NO dispara TASK_COMPLETED."""
        AutomationRule.objects.create(
            owner=user,
            name="On complete",
            trigger=AutomationRule.Trigger.TASK_COMPLETED,
            action=AutomationRule.Action.CREATE_NOTIFICATION,
            action_params={"title": "Should not fire"},
            enabled=True,
        )
        task.state = Task.State.IN_PROGRESS
        task.save()
        logs = AutomationLog.objects.filter(
            rule__trigger=AutomationRule.Trigger.TASK_COMPLETED
        )
        assert not logs.exists()


# --- SPRINT_STARTED trigger ---

@pytest.mark.django_db
class TestSprintStartedTrigger:
    def test_sprint_started_triggers_automation(self, user, project):
        """Activar un sprint dispara SPRINT_STARTED."""
        from django.utils import timezone
        sprint = Sprint.objects.create(
            owner=user, project=project, name="Sprint 1",
            state=Sprint.SprintState.PLANNED,
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timezone.timedelta(days=14),
        )
        AutomationRule.objects.create(
            owner=user,
            name="On sprint start",
            trigger=AutomationRule.Trigger.SPRINT_STARTED,
            action=AutomationRule.Action.CREATE_NOTIFICATION,
            action_params={"title": "Sprint started!"},
            enabled=True,
        )
        sprint.state = Sprint.SprintState.ACTIVE
        sprint.save()
        logs = AutomationLog.objects.filter(
            rule__trigger=AutomationRule.Trigger.SPRINT_STARTED
        )
        assert logs.exists()
        assert logs.first().status == AutomationLog.Status.SUCCESS

    def test_sprint_closed_does_not_trigger_started(self, user, project):
        """Cerrar un sprint NO dispara SPRINT_STARTED."""
        from django.utils import timezone
        sprint = Sprint.objects.create(
            owner=user, project=project, name="Sprint 2",
            state=Sprint.SprintState.ACTIVE,
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timezone.timedelta(days=14),
        )
        AutomationRule.objects.create(
            owner=user,
            name="On sprint start",
            trigger=AutomationRule.Trigger.SPRINT_STARTED,
            action=AutomationRule.Action.CREATE_NOTIFICATION,
            action_params={"title": "Should not fire"},
            enabled=True,
        )
        sprint.state = Sprint.SprintState.CLOSED
        sprint.save()
        logs = AutomationLog.objects.filter(
            rule__trigger=AutomationRule.Trigger.SPRINT_STARTED
        )
        assert not logs.exists()


# --- DAILY_CHECK trigger ---

@pytest.mark.django_db
class TestDailyCheckTrigger:
    def test_daily_check_triggers_automation(self, user):
        """run_daily_checks dispara DAILY_CHECK para usuarios con reglas habilitadas."""
        AutomationRule.objects.create(
            owner=user,
            name="Daily reminder",
            trigger=AutomationRule.Trigger.DAILY_CHECK,
            action=AutomationRule.Action.CREATE_NOTIFICATION,
            action_params={"title": "Daily check!", "body": "Don't forget your tasks"},
            enabled=True,
        )
        from apps.automations.engine import run_daily_checks
        run_daily_checks()
        logs = AutomationLog.objects.filter(
            rule__trigger=AutomationRule.Trigger.DAILY_CHECK
        )
        assert logs.exists()
        assert logs.first().status == AutomationLog.Status.SUCCESS

    def test_daily_check_no_rules_no_logs(self, user):
        """Si no hay reglas DAILY_CHECK, no se crean logs."""
        from apps.automations.engine import run_daily_checks
        run_daily_checks()
        logs = AutomationLog.objects.filter(
            rule__trigger=AutomationRule.Trigger.DAILY_CHECK
        )
        assert not logs.exists()
