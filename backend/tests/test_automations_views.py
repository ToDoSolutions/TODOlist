import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.automations.models import AutomationLog, AutomationRule
from apps.tasks.models import Task

User = get_user_model()


@pytest.fixture
def auth_client(db):
    user = User.objects.create_user(username="av", email="av@av.com", password="pass")
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return client, user


@pytest.mark.django_db
class TestAutomationRuleViewSet:
    def test_list_rules(self, auth_client):
        client, user = auth_client
        AutomationRule.objects.create(owner=user, name="R1", trigger="task_created", action="set_priority")
        AutomationRule.objects.create(owner=User.objects.create_user(username="o", email="o@o.com", password="p"), name="R2", trigger="task_created", action="set_priority")
        resp = client.get("/api/automation-rules/")
        assert resp.status_code == 200
        assert len(resp.data) == 1

    def test_create_rule(self, auth_client):
        client, user = auth_client
        resp = client.post("/api/automation-rules/", {
            "name": "R1", "trigger": "task_created", "action": "set_priority",
            "action_params": {"priority": 1},
        }, format="json")
        assert resp.status_code == 201
        assert AutomationRule.objects.filter(owner=user, name="R1").exists()

    def test_update_rule(self, auth_client):
        client, user = auth_client
        rule = AutomationRule.objects.create(owner=user, name="R1", trigger="task_created", action="set_priority")
        resp = client.patch(f"/api/automation-rules/{rule.id}/", {"enabled": False})
        assert resp.status_code == 200
        rule.refresh_from_db()
        assert rule.enabled is False

    def test_delete_rule(self, auth_client):
        client, user = auth_client
        rule = AutomationRule.objects.create(owner=user, name="R1", trigger="task_created", action="set_priority")
        resp = client.delete(f"/api/automation-rules/{rule.id}/")
        assert resp.status_code == 204
        assert not AutomationRule.objects.filter(id=rule.id).exists()

    def test_test_rule(self, auth_client):
        client, user = auth_client
        rule = AutomationRule.objects.create(owner=user, name="R1", trigger="task_created", action="set_priority", action_params={"priority": 1})
        Task.objects.create(owner=user, title="T")
        resp = client.post(f"/api/automation-rules/{rule.id}/test/")
        assert resp.status_code == 200
        assert "conditions_met" in resp.data
        assert "would_execute" in resp.data
        assert resp.data["would_execute"] is True

    def test_logs(self, auth_client):
        client, user = auth_client
        rule = AutomationRule.objects.create(owner=user, name="R1", trigger="task_created", action="set_priority")
        AutomationLog.objects.create(rule=rule, status="success", trigger_data={}, action_result={})
        resp = client.get(f"/api/automation-rules/{rule.id}/logs/")
        assert resp.status_code == 200
        assert len(resp.data) == 1

    def test_logs_other_user(self, auth_client):
        client, _ = auth_client
        other = User.objects.create_user(username="o2", email="o2@o.com", password="p")
        rule = AutomationRule.objects.create(owner=other, name="R1", trigger="task_created", action="set_priority")
        resp = client.get(f"/api/automation-rules/{rule.id}/logs/")
        assert resp.status_code == 404


@pytest.mark.django_db
class TestAutomationLogViewSet:
    def test_list_logs(self, auth_client):
        client, user = auth_client
        rule = AutomationRule.objects.create(owner=user, name="R1", trigger="task_created", action="set_priority")
        AutomationLog.objects.create(rule=rule, status="success", trigger_data={}, action_result={})
        other = User.objects.create_user(username="o3", email="o3@o.com", password="p")
        other_rule = AutomationRule.objects.create(owner=other, name="R2", trigger="task_created", action="set_priority")
        AutomationLog.objects.create(rule=other_rule, status="failed", trigger_data={}, action_result={})
        resp = client.get("/api/automation-logs/")
        assert resp.status_code == 200
        assert len(resp.data) == 1
        assert resp.data[0]["status"] == "success"
