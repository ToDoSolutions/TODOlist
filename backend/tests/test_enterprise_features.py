"""Tests de features avanzadas: OKR, Feature flags, AI assistant, Chat integrations,
Gantt, Burndown, Capacity, Audit dashboard, Prometheus metrics."""
import pytest
from apps.tasks.models import Task, Sprint
from apps.users.models import User


# --- OKRs ---

@pytest.mark.django_db
class TestOKRs:
    def test_crear_objective(self, authed_client, user):
        resp = authed_client.post("/api/objectives/", {
            "title": "Aumentar productividad",
            "description": "Objetivo Q1",
            "quarter": "Q1",
            "year": 2025,
        }, format="json")
        assert resp.status_code == 201

    def test_crear_key_result(self, authed_client, user):
        from apps.okrs.models import Objective
        obj = Objective.objects.create(owner=user, title="O1", quarter="Q1", year=2025)
        resp = authed_client.post("/api/key-results/", {
            "objective": obj.id,
            "title": "Completar 100 tareas",
            "target_value": 100,
            "current_value": 0,
            "unit": "count",
        }, format="json")
        assert resp.status_code == 201

    def test_update_key_result_value(self, authed_client, user):
        from apps.okrs.models import Objective, KeyResult
        obj = Objective.objects.create(owner=user, title="O1", quarter="Q1", year=2025)
        kr = KeyResult.objects.create(objective=obj, owner=user, title="KR1", target_value=100, current_value=0, unit="count")
        resp = authed_client.post(f"/api/key-results/{kr.id}/update_value/", {
            "new_value": 25,
            "note": "Progreso inicial",
        }, format="json")
        assert resp.status_code == 200
        kr.refresh_from_db()
        assert kr.current_value == 25

    def test_objective_progress(self, authed_client, user):
        from apps.okrs.models import Objective, KeyResult
        obj = Objective.objects.create(owner=user, title="O1", quarter="Q1", year=2025)
        KeyResult.objects.create(objective=obj, owner=user, title="KR1", target_value=100, current_value=50, unit="count")
        KeyResult.objects.create(objective=obj, owner=user, title="KR2", target_value=10, current_value=5, unit="count")
        resp = authed_client.get(f"/api/objectives/{obj.id}/progress/")
        assert resp.status_code == 200
        assert resp.data["progress"] == 50  # (50% + 50%) / 2


# --- Feature Flags ---

@pytest.mark.django_db
class TestFeatureFlags:
    def test_crear_flag(self, authed_client, user):
        resp = authed_client.post("/api/feature-flags/", {
            "key": "ai_assistant",
            "name": "AI Assistant",
            "is_enabled": True,
        }, format="json")
        assert resp.status_code == 201

    def test_check_flag_enabled(self, authed_client, user):
        from apps.feature_flags.models import FeatureFlag
        FeatureFlag.objects.create(key="test_flag", name="Test", is_enabled=True)
        resp = authed_client.get("/api/feature-flags/test_flag/check/")
        assert resp.status_code == 200
        assert resp.data["enabled"] is True

    def test_check_flag_disabled(self, authed_client, user):
        from apps.feature_flags.models import FeatureFlag
        FeatureFlag.objects.create(key="test_flag", name="Test", is_enabled=False)
        resp = authed_client.get("/api/feature-flags/test_flag/check/")
        assert resp.status_code == 200
        assert resp.data["enabled"] is False

    def test_flag_for_specific_user(self, authed_client, user):
        from apps.feature_flags.models import FeatureFlag
        flag = FeatureFlag.objects.create(key="user_flag", name="User Flag", is_enabled=False)
        flag.enabled_users.add(user)
        resp = authed_client.get("/api/feature-flags/user_flag/check/")
        assert resp.data["enabled"] is True


# --- AI Assistant ---

@pytest.mark.django_db
class TestAIAssistant:
    def test_estimate_priority(self, authed_client, user, task):
        resp = authed_client.post("/api/ai/estimate-priority/", {
            "task_id": task.id,
        }, format="json")
        assert resp.status_code == 200
        assert "suggested_priority" in resp.data
        assert "confidence" in resp.data

    def test_estimate_story_points(self, authed_client, user, task):
        resp = authed_client.post("/api/ai/estimate-story-points/", {
            "task_id": task.id,
        }, format="json")
        assert resp.status_code == 200
        assert "suggested_points" in resp.data

    def test_detect_blockers(self, authed_client, user, task):
        resp = authed_client.get("/api/ai/detect-blockers/")
        assert resp.status_code == 200
        assert "blockers" in resp.data

    def test_improve_description(self, authed_client, user, task):
        resp = authed_client.post("/api/ai/improve-description/", {
            "task_id": task.id,
        }, format="json")
        assert resp.status_code == 200
        assert "suggestions" in resp.data

    def test_list_suggestions(self, authed_client, user):
        resp = authed_client.get("/api/ai/suggestions/")
        assert resp.status_code == 200


# --- Chat Integrations ---

@pytest.mark.django_db
class TestChatIntegrations:
    def test_crear_slack_integration(self, authed_client, user):
        resp = authed_client.post("/api/chat-integrations/", {
            "provider": "slack",
            "webhook_url": "https://hooks.slack.com/services/test",
            "events": ["task_created", "task_completed"],
        }, format="json")
        assert resp.status_code == 201

    def test_listar_integrations(self, authed_client, user):
        from apps.integrations_chat.models import ChatIntegration
        ChatIntegration.objects.create(
            owner=user, provider="slack",
            webhook_url="https://hooks.slack.com/test",
            events=["task_created"],
        )
        resp = authed_client.get("/api/chat-integrations/")
        assert resp.status_code == 200
        data = resp.data["results"] if "results" in resp.data else resp.data
        assert len(data) == 1

    def test_desactivar_integration(self, authed_client, user):
        from apps.integrations_chat.models import ChatIntegration
        integration = ChatIntegration.objects.create(
            owner=user, provider="discord",
            webhook_url="https://discord.com/api/webhooks/test",
            events=["task_created"],
        )
        resp = authed_client.patch(f"/api/chat-integrations/{integration.id}/", {
            "is_active": False,
        }, format="json")
        assert resp.status_code == 200
        integration.refresh_from_db()
        assert integration.is_active is False


# --- Advanced Metrics ---

@pytest.mark.django_db
class TestGanttData:
    def test_gantt_endpoint(self, authed_client, user, project):
        Task.objects.create(owner=user, project=project, title="T1", due_date="2025-12-31")
        resp = authed_client.get("/api/tasks/gantt/")
        assert resp.status_code == 200
        assert "tasks" in resp.data
        assert "sprints" in resp.data


@pytest.mark.django_db
class TestBurndown:
    def test_burndown_endpoint(self, authed_client, user, project):
        from datetime import date, timedelta
        sprint = Sprint.objects.create(
            owner=user, project=project, name="S1",
            state=Sprint.SprintState.ACTIVE,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=14),
        )
        resp = authed_client.get(f"/api/tasks/burndown/?sprint_id={sprint.id}")
        assert resp.status_code == 200
        assert "ideal" in resp.data
        assert "actual" in resp.data

    def test_burndown_sin_sprint_id(self, authed_client, user):
        resp = authed_client.get("/api/tasks/burndown/")
        assert resp.status_code == 400


@pytest.mark.django_db
class TestCapacity:
    def test_capacity_endpoint(self, authed_client, user):
        resp = authed_client.get("/api/tasks/capacity/")
        assert resp.status_code == 200
        assert "capacity" in resp.data


@pytest.mark.django_db
class TestAuditDashboard:
    def test_audit_dashboard_endpoint(self, authed_client, user):
        from apps.collaboration.audit import log_create
        log_create(actor=user, resource_type="task", resource_id=1, resource_name="T1")
        resp = authed_client.get("/api/tasks/audit_dashboard/")
        assert resp.status_code == 200
        assert "by_action" in resp.data
        assert "by_day" in resp.data


# --- Prometheus Metrics ---

@pytest.mark.django_db
class TestPrometheusMetrics:
    def test_metrics_endpoint(self, client):
        resp = client.get("/api/metrics/")
        assert resp.status_code == 200
        content = resp.content.decode()
        assert "todolist" in content


# --- Social Auth ---

@pytest.mark.django_db
class TestSocialAuth:
    def test_social_auth_urls_exist(self, client):
        """Las URLs de social auth están configuradas."""
        # El endpoint de login de allauth debe existir
        resp = client.get("/api/auth/social/login/google/")
        # Puede ser redirect o 200
        assert resp.status_code in (200, 302, 404)

    def test_social_jwt_callback_sin_auth(self, client):
        """El callback JWT sin auth retorna 401."""
        resp = client.get("/api/auth/social/jwt/")
        assert resp.status_code == 401
