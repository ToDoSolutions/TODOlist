import pytest
from django.contrib.auth import get_user_model

from apps.ai_assistant.models import AiSuggestion
from apps.tasks.models import Task

User = get_user_model()


@pytest.mark.django_db
class TestAiSuggestion:
    @pytest.fixture(autouse=True)
    def setup_data(self, db):
        self.user = User.objects.create_user(username="am", email="am@am.com", password="pass")
        self.task = Task.objects.create(owner=self.user, title="T")

    def test_str(self):
        s = AiSuggestion.objects.create(user=self.user, task=self.task, suggestion_type="priority_estimate")
        assert "priority_estimate" in str(s)
        assert str(self.user.id) in str(s)
        assert str(self.task.id) in str(s)

    def test_str_no_task(self):
        s = AiSuggestion.objects.create(user=self.user, task=None, suggestion_type="blocker_detection")
        assert "blocker_detection" in str(s)
        assert str(self.user.id) in str(s)
        assert "None" in str(s)

    def test_ordering(self):
        s1 = AiSuggestion.objects.create(user=self.user, task=self.task, suggestion_type="priority_estimate")
        s2 = AiSuggestion.objects.create(user=self.user, task=self.task, suggestion_type="story_point_estimate")
        from django.utils import timezone as _tz
        AiSuggestion.objects.filter(pk=s1.pk).update(created_at=_tz.now() - _tz.timedelta(hours=1))
        suggestions = list(AiSuggestion.objects.all())
        assert suggestions[0] == s2  # ordering by -created_at

    def test_choices(self):
        assert AiSuggestion.SuggestionType.PRIORITY_ESTIMATE == "priority_estimate"
        assert AiSuggestion.SuggestionType.STORY_POINT_ESTIMATE == "story_point_estimate"
        assert AiSuggestion.SuggestionType.BLOCKER_DETECTION == "blocker_detection"
        assert AiSuggestion.SuggestionType.DESCRIPTION_IMPROVEMENT == "description_improvement"

    def test_status_choices(self):
        s = AiSuggestion.objects.create(user=self.user, task=self.task, suggestion_type="priority_estimate")
        assert s.status == "pending"
        s.status = "accepted"
        s.save()
        s.refresh_from_db()
        assert s.status == "accepted"

    def test_defaults(self):
        s = AiSuggestion.objects.create(user=self.user, task=self.task, suggestion_type="priority_estimate")
        assert s.input_data == {}
        assert s.output_data == {}
        assert s.confidence == 0.0
        assert s.status == "pending"
