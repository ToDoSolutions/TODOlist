"""Tests exhaustivos para modelos de ai_assistant."""
import pytest
from django.contrib.auth import get_user_model

from apps.ai_assistant.models import AiSuggestion
from apps.tasks.models import Task

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="ai", email="ai@ai.com", password="pass")


@pytest.mark.django_db
class TestAiSuggestion:
    def test_str(self, user):
        s = AiSuggestion.objects.create(
            user=user, suggestion_type="priority_estimate"
        )
        assert "priority_estimate" in str(s)
        assert str(user.id) in str(s)

    def test_suggestion_type_choices(self):
        assert AiSuggestion.SuggestionType.PRIORITY_ESTIMATE == "priority_estimate"
        assert AiSuggestion.SuggestionType.STORY_POINT_ESTIMATE == "story_point_estimate"
        assert AiSuggestion.SuggestionType.BLOCKER_DETECTION == "blocker_detection"
        assert AiSuggestion.SuggestionType.DESCRIPTION_IMPROVEMENT == "description_improvement"

    def test_status_choices(self):
        # status es CharField con choices inline
        s = AiSuggestion(status="pending")
        assert s.status == "pending"
        s.status = "accepted"
        assert s.status == "accepted"
        s.status = "rejected"
        assert s.status == "rejected"
        s.status = "applied"
        assert s.status == "applied"

    def test_defaults(self, user):
        s = AiSuggestion.objects.create(user=user, suggestion_type="priority_estimate")
        assert s.task is None
        assert s.input_data == {}
        assert s.output_data == {}
        assert s.confidence == 0.0
        assert s.status == "pending"

    def test_ordering(self, user):
        s1 = AiSuggestion.objects.create(user=user, suggestion_type="priority_estimate")
        s2 = AiSuggestion.objects.create(user=user, suggestion_type="story_point_estimate")
        from django.utils import timezone as _tz
        AiSuggestion.objects.filter(pk=s1.pk).update(created_at=_tz.now() - _tz.timedelta(hours=1))
        suggestions = list(AiSuggestion.objects.all())
        assert suggestions[0] == s2  # ordering by -created_at

    def test_task_relation(self, user):
        task = Task.objects.create(owner=user, title="Task 1")
        s = AiSuggestion.objects.create(
            user=user, task=task, suggestion_type="priority_estimate"
        )
        assert s.task == task
        assert task.ai_suggestions.count() == 1
