"""Tests exhaustivos para automations/views.py."""
import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from apps.automations.models import AutomationLog, AutomationRule

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="av", email="av@av.com", password="pass")


@pytest.fixture
def api_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
class TestAutomationRuleViewSet:
    def test_test_action(self, api_client, user):
        """Verifica que la acción test simula la regla sin ejecutarla."""
        rule = AutomationRule.objects.create(
            owner=user, name="Test Rule", trigger="task_created", action="set_priority"
        )
        response = api_client.post(f"/api/automation-rules/{rule.id}/test/")
        assert response.status_code == status.HTTP_200_OK
        assert "conditions_met" in response.data
        assert "would_execute" in response.data
        # Sin tareas del usuario, no ejecutaría
        assert response.data["would_execute"] is False

    def test_test_action_with_task(self, api_client, user):
        """Con una tarea existente, would_execute es True."""
        from apps.tasks.models import Task
        Task.objects.create(owner=user, title="T")
        rule = AutomationRule.objects.create(
            owner=user, name="Test Rule", trigger="task_created", action="set_priority"
        )
        response = api_client.post(f"/api/automation-rules/{rule.id}/test/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["would_execute"] is True

    def test_logs_action(self, api_client, user):
        """Verifica que la acción logs retorna historial."""
        rule = AutomationRule.objects.create(
            owner=user, name="Test Rule", trigger="task_created", action="set_priority"
        )
        AutomationLog.objects.create(rule=rule, status="success")
        response = api_client.get(f"/api/automation-rules/{rule.id}/logs/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1

    def test_logs_empty(self, api_client, user):
        """Verifica que logs retorna lista vacía si no hay logs."""
        rule = AutomationRule.objects.create(
            owner=user, name="Test Rule", trigger="task_created", action="set_priority"
        )
        response = api_client.get(f"/api/automation-rules/{rule.id}/logs/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 0

    def test_test_action_other_user(self, api_client):
        """Verifica que test de regla de otro usuario retorna 404."""
        other = User.objects.create_user(username="other", email="other@other.com", password="pass")
        rule = AutomationRule.objects.create(
            owner=other, name="Other Rule", trigger="task_created", action="set_priority"
        )
        response = api_client.post(f"/api/automation-rules/{rule.id}/test/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestAutomationLogViewSet:
    def test_list(self, api_client, user):
        """Verifica que lista logs del usuario."""
        rule = AutomationRule.objects.create(
            owner=user, name="Test Rule", trigger="task_created", action="set_priority"
        )
        AutomationLog.objects.create(rule=rule, status="success")
        response = api_client.get("/api/automation-logs/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1

    def test_list_filters_by_user(self, api_client):
        """Verifica que solo lista logs del usuario autenticado."""
        other = User.objects.create_user(username="other", email="other@other.com", password="pass")
        rule = AutomationRule.objects.create(
            owner=other, name="Other Rule", trigger="task_created", action="set_priority"
        )
        AutomationLog.objects.create(rule=rule, status="success")
        response = api_client.get("/api/automation-logs/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 0
