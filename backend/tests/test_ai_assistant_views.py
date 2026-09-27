import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.ai_assistant.models import AiSuggestion
from apps.tasks.models import Task

User = get_user_model()


@pytest.mark.django_db
class TestAiAssistantViews:
    @pytest.fixture(autouse=True)
    def setup_data(self, db):
        self.user = User.objects.create_user(username="ai", email="ai@ai.com", password="pass")
        self.other = User.objects.create_user(username="ai2", email="ai2@ai.com", password="pass")
        self.task = Task.objects.create(owner=self.user, title="T", state="pending", priority=3)
        self.client = APIClient()
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

    def test_estimate_priority(self):
        resp = self.client.post("/api/ai/estimate-priority/", {"task_id": self.task.id})
        assert resp.status_code == 200
        assert "suggested_priority" in resp.data
        assert "confidence" in resp.data
        assert AiSuggestion.objects.filter(suggestion_type="priority_estimate", task=self.task).exists()

    def test_estimate_priority_not_found(self):
        resp = self.client.post("/api/ai/estimate-priority/", {"task_id": 999})
        assert resp.status_code == 404

    def test_estimate_priority_other_user(self):
        other_task = Task.objects.create(owner=self.other, title="T2")
        resp = self.client.post("/api/ai/estimate-priority/", {"task_id": other_task.id})
        assert resp.status_code == 404

    def test_estimate_story_points(self):
        resp = self.client.post("/api/ai/estimate-story-points/", {"task_id": self.task.id})
        assert resp.status_code == 200
        assert "suggested_points" in resp.data
        assert AiSuggestion.objects.filter(suggestion_type="story_point_estimate", task=self.task).exists()

    def test_detect_blockers(self):
        resp = self.client.get("/api/ai/detect-blockers/")
        assert resp.status_code == 200
        assert "blockers" in resp.data
        assert AiSuggestion.objects.filter(suggestion_type="blocker_detection", task=None).exists()

    def test_improve_description(self):
        resp = self.client.post("/api/ai/improve-description/", {"task_id": self.task.id})
        assert resp.status_code == 200
        assert "suggestions" in resp.data
        assert AiSuggestion.objects.filter(suggestion_type="description_improvement", task=self.task).exists()

    def test_suggestion_list(self):
        AiSuggestion.objects.create(user=self.user, task=self.task, suggestion_type="priority_estimate", output_data={"suggested_priority": 1})
        resp = self.client.get("/api/ai/suggestions/")
        assert resp.status_code == 200
        assert len(resp.data) == 1

    def test_suggestion_list_other_user(self):
        AiSuggestion.objects.create(user=self.other, task=self.task, suggestion_type="priority_estimate")
        resp = self.client.get("/api/ai/suggestions/")
        assert len(resp.data) == 0

    def test_suggestion_action_accept(self):
        sugg = AiSuggestion.objects.create(user=self.user, task=self.task, suggestion_type="priority_estimate", output_data={"suggested_priority": 1})
        resp = self.client.post(f"/api/ai/suggestions/{sugg.id}/action/", {"action": "accept"})
        assert resp.status_code == 200
        sugg.refresh_from_db()
        assert sugg.status == "accepted"

    def test_suggestion_action_reject(self):
        sugg = AiSuggestion.objects.create(user=self.user, task=self.task, suggestion_type="priority_estimate")
        resp = self.client.post(f"/api/ai/suggestions/{sugg.id}/action/", {"action": "reject"})
        assert resp.status_code == 200
        sugg.refresh_from_db()
        assert sugg.status == "rejected"

    def test_suggestion_action_apply_priority(self):
        sugg = AiSuggestion.objects.create(user=self.user, task=self.task, suggestion_type="priority_estimate", output_data={"suggested_priority": 0})
        resp = self.client.post(f"/api/ai/suggestions/{sugg.id}/action/", {"action": "apply"})
        assert resp.status_code == 200
        self.task.refresh_from_db()
        assert self.task.priority == 0
        sugg.refresh_from_db()
        assert sugg.status == "applied"

    def test_suggestion_action_apply_story_points(self):
        sugg = AiSuggestion.objects.create(user=self.user, task=self.task, suggestion_type="story_point_estimate", output_data={"suggested_points": 8})
        resp = self.client.post(f"/api/ai/suggestions/{sugg.id}/action/", {"action": "apply"})
        assert resp.status_code == 200
        self.task.refresh_from_db()
        assert self.task.story_points == 8
        sugg.refresh_from_db()
        assert sugg.status == "applied"

    def test_suggestion_action_apply_description(self):
        sugg = AiSuggestion.objects.create(user=self.user, task=self.task, suggestion_type="description_improvement", output_data={"suggestions": ["New description"]})
        old_desc = self.task.description
        resp = self.client.post(f"/api/ai/suggestions/{sugg.id}/action/", {"action": "apply"})
        # Las sugerencias de descripción son orientativas: no se auto-aplican
        assert resp.status_code == 400
        self.task.refresh_from_db()
        assert self.task.description == old_desc
        sugg.refresh_from_db()
        assert sugg.status == "pending"

    def test_suggestion_action_apply_no_task(self):
        sugg = AiSuggestion.objects.create(user=self.user, task=None, suggestion_type="blocker_detection")
        resp = self.client.post(f"/api/ai/suggestions/{sugg.id}/action/", {"action": "apply"})
        assert resp.status_code == 400
        assert "no tiene tarea" in resp.data["error"]

    def test_suggestion_action_invalid(self):
        sugg = AiSuggestion.objects.create(user=self.user, task=self.task, suggestion_type="priority_estimate")
        resp = self.client.post(f"/api/ai/suggestions/{sugg.id}/action/", {"action": "invalid"})
        assert resp.status_code == 400
        assert "Acción no válida" in resp.data["error"]

    def test_suggestion_action_other_user(self):
        sugg = AiSuggestion.objects.create(user=self.other, task=self.task, suggestion_type="priority_estimate")
        resp = self.client.post(f"/api/ai/suggestions/{sugg.id}/action/", {"action": "accept"})
        assert resp.status_code == 404
