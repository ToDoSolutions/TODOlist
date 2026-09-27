"""Tests dirigidos para matar mutantes en apps.ai_assistant.views."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.ai_assistant import services
from apps.ai_assistant.models import AiSuggestion
from apps.tasks.models import Task


@pytest.mark.django_db
class TestAIAssistantMutationKills:
    def test_list_suggestions_filtered_by_user(self, authed_client, user, other_user, task):
        """SuggestionListView filtra por request.user."""
        AiSuggestion.objects.create(user=user, task=task, suggestion_type="priority_estimate")
        AiSuggestion.objects.create(user=other_user, task=task, suggestion_type="priority_estimate")

        resp = authed_client.get("/api/ai/suggestions/")
        assert resp.status_code == 200
        assert len(resp.data) == 1
        assert resp.data[0]["user"] == user.id

    def test_estimate_priority_uses_requested_task(self, authed_client, user, task):
        """EstimatePriorityView usa task_id y crea AiSuggestion correcta."""
        Task.objects.create(owner=user, title="Otra tarea", state="pending")
        resp = authed_client.post("/api/ai/estimate-priority/", {
            "task_id": task.id,
        }, format="json")
        assert resp.status_code == 200

        expected = services.estimate_priority(task)
        assert resp.data["suggested_priority"] == expected["suggested_priority"]

        suggestion = AiSuggestion.objects.get(
            user=user, suggestion_type=AiSuggestion.SuggestionType.PRIORITY_ESTIMATE
        )
        assert suggestion.task == task
        assert suggestion.input_data == {"task_id": task.id}
        assert suggestion.output_data == expected
        assert suggestion.confidence == expected["confidence"]

    def test_estimate_priority_other_user_task_returns_404(self, authed_client, other_user):
        """No puede estimar prioridad de tarea ajena."""
        other_task = Task.objects.create(owner=other_user, title="Tarea ajena", state="pending")
        resp = authed_client.post("/api/ai/estimate-priority/", {
            "task_id": other_task.id,
        }, format="json")
        assert resp.status_code == 404

    def test_estimate_story_points_uses_requested_task(self, authed_client, user, task):
        """EstimateStoryPointsView usa task_id y crea AiSuggestion correcta."""
        Task.objects.create(owner=user, title="Otra tarea", state="pending")
        resp = authed_client.post("/api/ai/estimate-story-points/", {
            "task_id": task.id,
        }, format="json")
        assert resp.status_code == 200

        expected = services.estimate_story_points(task)
        assert resp.data["suggested_points"] == expected["suggested_points"]

        suggestion = AiSuggestion.objects.get(
            user=user, suggestion_type=AiSuggestion.SuggestionType.STORY_POINT_ESTIMATE
        )
        assert suggestion.task == task
        assert suggestion.input_data == {"task_id": task.id}
        assert suggestion.output_data == expected
        assert suggestion.confidence == expected["confidence"]

    def test_improve_description_uses_requested_task(self, authed_client, user, task):
        """ImproveDescriptionView usa task_id y crea AiSuggestion correcta."""
        Task.objects.create(owner=user, title="Otra tarea", state="pending")
        resp = authed_client.post("/api/ai/improve-description/", {
            "task_id": task.id,
        }, format="json")
        assert resp.status_code == 200

        expected = services.improve_description(task)
        assert resp.data == expected

        suggestion = AiSuggestion.objects.get(
            user=user, suggestion_type=AiSuggestion.SuggestionType.DESCRIPTION_IMPROVEMENT
        )
        assert suggestion.task == task
        assert suggestion.input_data == {"task_id": task.id, "description": task.description}
        assert suggestion.output_data == expected
        assert suggestion.confidence == expected["confidence"]

    def test_detect_blockers_empty_confidence_095(self, authed_client, user):
        """DetectBlockersView sin bloqueos devuelve [] y confidence 0.95."""
        resp = authed_client.get("/api/ai/detect-blockers/")
        assert resp.status_code == 200
        assert resp.data == {"blockers": []}

        suggestion = AiSuggestion.objects.get(
            user=user, suggestion_type=AiSuggestion.SuggestionType.BLOCKER_DETECTION
        )
        assert suggestion.output_data == {"blockers": []}
        assert suggestion.confidence == 0.95

    def test_detect_blockers_with_overdue_confidence_08(self, authed_client, user, task):
        """DetectBlockersView con bloqueos devuelve blockers y confidence 0.8."""
        task.due_date = timezone.now() - timedelta(days=1)
        task.state = Task.State.PENDING
        task.save(update_fields=["due_date", "state"])

        resp = authed_client.get("/api/ai/detect-blockers/")
        assert resp.status_code == 200
        assert len(resp.data["blockers"]) >= 1
        assert any(b["blocker_type"] == "overdue" for b in resp.data["blockers"])

        suggestion = AiSuggestion.objects.get(
            user=user, suggestion_type=AiSuggestion.SuggestionType.BLOCKER_DETECTION
        )
        assert len(suggestion.output_data["blockers"]) >= 1
        assert suggestion.confidence == 0.8

    def test_suggestion_action_accept(self, authed_client, user, task):
        """Aceptar sugerencia actualiza status."""
        out = services.estimate_priority(task)
        suggestion = AiSuggestion.objects.create(
            user=user,
            task=task,
            suggestion_type=AiSuggestion.SuggestionType.PRIORITY_ESTIMATE,
            output_data=out,
            confidence=out["confidence"],
        )
        resp = authed_client.post(f"/api/ai/suggestions/{suggestion.id}/action/", {
            "action": "accept",
        }, format="json")
        assert resp.status_code == 200
        suggestion.refresh_from_db()
        assert suggestion.status == "accepted"

    def test_suggestion_action_reject(self, authed_client, user, task):
        """Rechazar sugerencia actualiza status."""
        out = services.estimate_priority(task)
        suggestion = AiSuggestion.objects.create(
            user=user,
            task=task,
            suggestion_type=AiSuggestion.SuggestionType.PRIORITY_ESTIMATE,
            output_data=out,
            confidence=out["confidence"],
        )
        resp = authed_client.post(f"/api/ai/suggestions/{suggestion.id}/action/", {
            "action": "reject",
        }, format="json")
        assert resp.status_code == 200
        suggestion.refresh_from_db()
        assert suggestion.status == "rejected"

    def test_suggestion_action_apply_priority(self, authed_client, user, task):
        """Aplicar sugerencia de prioridad modifica la tarea."""
        out = services.estimate_priority(task)
        suggestion = AiSuggestion.objects.create(
            user=user,
            task=task,
            suggestion_type=AiSuggestion.SuggestionType.PRIORITY_ESTIMATE,
            output_data=out,
            confidence=out["confidence"],
        )
        resp = authed_client.post(f"/api/ai/suggestions/{suggestion.id}/action/", {
            "action": "apply",
        }, format="json")
        assert resp.status_code == 200
        task.refresh_from_db()
        assert task.priority == out["suggested_priority"]
        suggestion.refresh_from_db()
        assert suggestion.status == "applied"

    def test_suggestion_action_apply_description(self, authed_client, user, task):
        """Aplicar sugerencia de descripción modifica la tarea."""
        task.description = "corta"
        task.save(update_fields=["description"])
        out = services.improve_description(task)
        suggestion = AiSuggestion.objects.create(
            user=user,
            task=task,
            suggestion_type=AiSuggestion.SuggestionType.DESCRIPTION_IMPROVEMENT,
            output_data=out,
            confidence=out["confidence"],
        )
        resp = authed_client.post(f"/api/ai/suggestions/{suggestion.id}/action/", {
            "action": "apply",
        }, format="json")
        # Las sugerencias de descripción son consejos: apply devuelve 400
        # y no toca la tarea (antes escribía el consejo como descripción)
        assert resp.status_code == 400
        task.refresh_from_db()
        assert task.description == "corta"
        suggestion.refresh_from_db()
        assert suggestion.status == "pending"

    def test_suggestion_action_invalid(self, authed_client, user, task):
        """Acción inválida devuelve 400."""
        out = services.estimate_priority(task)
        suggestion = AiSuggestion.objects.create(
            user=user,
            task=task,
            suggestion_type=AiSuggestion.SuggestionType.PRIORITY_ESTIMATE,
            output_data=out,
            confidence=out["confidence"],
        )
        resp = authed_client.post(f"/api/ai/suggestions/{suggestion.id}/action/", {
            "action": "banana",
        }, format="json")
        assert resp.status_code == 400
        assert resp.data["error"] == "Acción no válida. Usa: accept, reject o apply"

    def test_suggestion_action_accept_message(self, authed_client, user, task):
        """Mensaje de aceptación exacto."""
        out = services.estimate_priority(task)
        suggestion = AiSuggestion.objects.create(
            user=user,
            task=task,
            suggestion_type=AiSuggestion.SuggestionType.PRIORITY_ESTIMATE,
            output_data=out,
            confidence=out["confidence"],
        )
        resp = authed_client.post(f"/api/ai/suggestions/{suggestion.id}/action/", {
            "action": "accept",
        }, format="json")
        assert resp.data["message"] == "Sugerencia aceptada"

    def test_suggestion_action_reject_message(self, authed_client, user, task):
        """Mensaje de rechazo exacto."""
        out = services.estimate_priority(task)
        suggestion = AiSuggestion.objects.create(
            user=user,
            task=task,
            suggestion_type=AiSuggestion.SuggestionType.PRIORITY_ESTIMATE,
            output_data=out,
            confidence=out["confidence"],
        )
        resp = authed_client.post(f"/api/ai/suggestions/{suggestion.id}/action/", {
            "action": "reject",
        }, format="json")
        assert resp.data["message"] == "Sugerencia rechazada"

    def test_suggestion_action_apply_specific_suggestion(self, authed_client, user, task):
        """Aplicar afecta solo la sugerencia indicada por pk."""
        out = services.estimate_priority(task)
        s1 = AiSuggestion.objects.create(
            user=user,
            task=task,
            suggestion_type=AiSuggestion.SuggestionType.PRIORITY_ESTIMATE,
            output_data=out,
            confidence=out["confidence"],
        )
        s2 = AiSuggestion.objects.create(
            user=user,
            task=task,
            suggestion_type=AiSuggestion.SuggestionType.PRIORITY_ESTIMATE,
            output_data={"suggested_priority": 0, "confidence": 0.9},
            confidence=0.9,
        )
        resp = authed_client.post(f"/api/ai/suggestions/{s2.id}/action/", {
            "action": "apply",
        }, format="json")
        assert resp.status_code == 200
        s1.refresh_from_db()
        s2.refresh_from_db()
        assert s1.status == "pending"
        assert s2.status == "applied"
        task.refresh_from_db()
        assert task.priority == 0

    def test_detect_blockers_input_data(self, authed_client, user):
        """DetectBlockersView guarda input_data con user_id."""
        resp = authed_client.get("/api/ai/detect-blockers/")
        assert resp.status_code == 200
        suggestion = AiSuggestion.objects.get(
            user=user, suggestion_type=AiSuggestion.SuggestionType.BLOCKER_DETECTION
        )
        assert suggestion.input_data == {"user_id": user.id}

    def test_improve_description_input_data(self, authed_client, user, task):
        """ImproveDescriptionView guarda input_data con task_id y description."""
        resp = authed_client.post("/api/ai/improve-description/", {
            "task_id": task.id,
        }, format="json")
        assert resp.status_code == 200
        suggestion = AiSuggestion.objects.get(
            user=user, suggestion_type=AiSuggestion.SuggestionType.DESCRIPTION_IMPROVEMENT
        )
        assert suggestion.input_data == {"task_id": task.id, "description": task.description}

    def test_estimate_priority_input_data(self, authed_client, user, task):
        """EstimatePriorityView guarda input_data con task_id."""
        resp = authed_client.post("/api/ai/estimate-priority/", {
            "task_id": task.id,
        }, format="json")
        assert resp.status_code == 200
        suggestion = AiSuggestion.objects.get(
            user=user, suggestion_type=AiSuggestion.SuggestionType.PRIORITY_ESTIMATE
        )
        assert suggestion.input_data == {"task_id": task.id}

    def test_estimate_story_points_input_data(self, authed_client, user, task):
        """EstimateStoryPointsView guarda input_data con task_id."""
        resp = authed_client.post("/api/ai/estimate-story-points/", {
            "task_id": task.id,
        }, format="json")
        assert resp.status_code == 200
        suggestion = AiSuggestion.objects.get(
            user=user, suggestion_type=AiSuggestion.SuggestionType.STORY_POINT_ESTIMATE
        )
        assert suggestion.input_data == {"task_id": task.id}
