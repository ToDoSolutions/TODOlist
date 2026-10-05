from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.ai_assistant.services import (
    detect_blockers,
    estimate_priority,
    estimate_story_points,
    improve_description,
)
from apps.tasks.models import Subtask, Task, TaskRelation

User = get_user_model()


@pytest.mark.django_db
class TestEstimatePriority:
    @pytest.fixture(autouse=True)
    def setup_data(self, db):
        self.user = User.objects.create_user(username="i", email="i@i.com", password="pass")

    def test_overdue_task(self):
        task = Task.objects.create(owner=self.user, title="T", due_date=timezone.now() - timedelta(days=1))
        result = estimate_priority(task)
        assert result["suggested_priority"] == 2
        assert "tarea vencida" in result["reasons"]

    def test_due_tomorrow(self):
        task = Task.objects.create(owner=self.user, title="T", due_date=timezone.now() + timedelta(hours=12))
        result = estimate_priority(task)
        assert result["suggested_priority"] == 2
        assert "vence en menos de 1 día" in result["reasons"]

    def test_due_in_3_days(self):
        task = Task.objects.create(owner=self.user, title="T", due_date=timezone.now() + timedelta(days=2))
        result = estimate_priority(task)
        assert result["suggested_priority"] == 3
        assert "vence en menos de 3 días" in result["reasons"]

    def test_due_in_7_days(self):
        task = Task.objects.create(owner=self.user, title="T", due_date=timezone.now() + timedelta(days=5))
        result = estimate_priority(task)
        assert "vence en menos de 7 días" in result["reasons"]

    def test_no_due_date(self):
        task = Task.objects.create(owner=self.user, title="T", priority=3)
        result = estimate_priority(task)
        assert result["suggested_priority"] == 4
        assert "prioridad crítica/muy alta" not in result["reasons"]

    def test_critical_priority(self):
        task = Task.objects.create(owner=self.user, title="T", priority=0)
        result = estimate_priority(task)
        assert "prioridad crítica/muy alta" in result["reasons"]

    def test_completed_task(self):
        task = Task.objects.create(owner=self.user, title="T", state="completed", priority=5)
        result = estimate_priority(task)
        assert result["suggested_priority"] == 5
        assert result["confidence"] == 0.9
        assert result["reasons"] == ["tarea inactiva"]

    def test_in_progress(self):
        task = Task.objects.create(owner=self.user, title="T", state="in_progress")
        result = estimate_priority(task)
        assert "en progreso" in result["reasons"]

    def test_blocked(self):
        task = Task.objects.create(owner=self.user, title="T", state="blocked")
        result = estimate_priority(task)
        assert "bloqueada" in result["reasons"]

    def test_blocks_others(self):
        task = Task.objects.create(owner=self.user, title="T")
        other = Task.objects.create(owner=self.user, title="T2")
        TaskRelation.objects.create(source=task, target=other, relation_type="blocks")
        result = estimate_priority(task)
        assert "bloquea a 1 tarea(s)" in result["reasons"]


@pytest.mark.django_db
class TestEstimateStoryPoints:
    @pytest.fixture(autouse=True)
    def setup_data(self, db):
        self.user = User.objects.create_user(username="j", email="j@j.com", password="pass")

    def test_no_description(self):
        task = Task.objects.create(owner=self.user, title="T", description="")
        result = estimate_story_points(task)
        assert result["suggested_points"] == 1
        assert "sin descripción" in result["reasons"]

    def test_short_description(self):
        task = Task.objects.create(owner=self.user, title="T", description="short")
        result = estimate_story_points(task)
        assert result["suggested_points"] == 2
        assert "descripción corta" in result["reasons"]

    def test_medium_description(self):
        task = Task.objects.create(owner=self.user, title="T", description="x" * 200)
        result = estimate_story_points(task)
        assert result["suggested_points"] == 3
        assert "descripción media" in result["reasons"]

    def test_long_description(self):
        task = Task.objects.create(owner=self.user, title="T", description="x" * 600)
        result = estimate_story_points(task)
        assert result["suggested_points"] == 5
        assert "descripción extensa" in result["reasons"]

    def test_many_subtasks(self):
        task = Task.objects.create(owner=self.user, title="T", description="x" * 600)
        for i in range(7):
            Subtask.objects.create(task=task, title=f"Sub{i}")
        result = estimate_story_points(task)
        assert result["suggested_points"] == 13
        assert "7 subtareas (muchas)" in result["reasons"]

    def test_depends_on(self):
        task = Task.objects.create(owner=self.user, title="T", description="x" * 200)
        dep = Task.objects.create(owner=self.user, title="Dep")
        TaskRelation.objects.create(source=task, target=dep, relation_type="depends_on")
        result = estimate_story_points(task)
        assert "depende de 1 tarea(s)" in result["reasons"]


@pytest.mark.django_db
class TestDetectBlockers:
    @pytest.fixture(autouse=True)
    def setup_data(self, db):
        self.user = User.objects.create_user(username="k", email="k@k.com", password="pass")

    def test_stale_in_progress(self):
        task = Task.objects.create(owner=self.user, title="T", state="in_progress")
        Task.objects.filter(id=task.id).update(updated_at=timezone.now() - timedelta(days=10))
        blockers = detect_blockers(self.user)
        assert len(blockers) == 1
        assert blockers[0]["blocker_type"] == "stale_in_progress"
        assert blockers[0]["severity"] == "medium"

    def test_dependency_unresolved(self):
        dep = Task.objects.create(owner=self.user, title="Dep", state="pending")
        task = Task.objects.create(owner=self.user, title="T")
        TaskRelation.objects.create(source=task, target=dep, relation_type="depends_on")
        blockers = detect_blockers(self.user)
        assert len(blockers) == 1
        assert blockers[0]["blocker_type"] == "dependency_unresolved"
        assert blockers[0]["severity"] == "high"

    def test_overdue(self):
        Task.objects.create(owner=self.user, title="T", state="pending", due_date=timezone.now() - timedelta(days=5))
        blockers = detect_blockers(self.user)
        assert len(blockers) == 1
        assert blockers[0]["blocker_type"] == "overdue"
        assert blockers[0]["severity"] == "high"

    def test_no_blockers(self):
        Task.objects.create(owner=self.user, title="T", state="completed")
        blockers = detect_blockers(self.user)
        assert blockers == []


@pytest.mark.django_db
class TestImproveDescription:
    @pytest.fixture(autouse=True)
    def setup_data(self, db):
        self.user = User.objects.create_user(username="l", email="l@l.com", password="pass")

    def test_no_description(self):
        task = Task.objects.create(owner=self.user, title="T", description="")
        result = improve_description(task)
        assert len(result["suggestions"]) == 2
        assert "no tiene descripción" in result["suggestions"][0]

    def test_short_description(self):
        task = Task.objects.create(owner=self.user, title="T", description="Short")
        result = improve_description(task)
        assert any("muy corta" in s for s in result["suggestions"])

    def test_missing_how(self):
        task = Task.objects.create(owner=self.user, title="T", description="Do the task")
        result = improve_description(task)
        assert any("cómo" in s for s in result["suggestions"])

    def test_missing_why(self):
        task = Task.objects.create(owner=self.user, title="T", description="Do the task")
        result = improve_description(task)
        assert any("por qué" in s for s in result["suggestions"])

    def test_missing_criteria(self):
        task = Task.objects.create(owner=self.user, title="T", description="Do the task")
        result = improve_description(task)
        assert any("criterios" in s for s in result["suggestions"])

    def test_complete_description(self):
        desc = "How to do it step by step. Why it matters for the project. Acceptance criteria: all tests pass and code is reviewed. " + "x" * 300
        task = Task.objects.create(owner=self.user, title="T", description=desc)
        result = improve_description(task)
        assert "parece completa" in result["suggestions"][0]
        assert result["confidence"] == 0.6

    def test_has_dependencies(self):
        dep = Task.objects.create(owner=self.user, title="Dep")
        task = Task.objects.create(owner=self.user, title="T", description="Do it")
        TaskRelation.objects.create(source=task, target=dep, relation_type="depends_on")
        result = improve_description(task)
        assert any("dependencias" in s for s in result["suggestions"])


@pytest.mark.django_db
class TestImproveDescriptionLLM:
    """BYOK: con LLM configurado usa el modelo; si falla, cae a heurísticas."""

    def test_llm_path(self, monkeypatch, settings, user):
        settings.AI_LLM_BASE_URL = "http://llm.test/v1"
        settings.AI_LLM_MODEL = "test-model"
        task = Task.objects.create(owner=user, title="T", description="Short")
        monkeypatch.setattr(
            "apps.ai_assistant.llm.chat",
            lambda *a, **k: '{"improved_description": "Mejor", "suggestions": ["S1"]}',
        )
        result = improve_description(task)
        assert result["source"] == "llm"
        assert result["improved_description"] == "Mejor"
        assert result["suggestions"] == ["S1"]

    def test_llm_failure_falls_back(self, monkeypatch, settings, user):
        settings.AI_LLM_BASE_URL = "http://llm.test/v1"
        settings.AI_LLM_MODEL = "test-model"
        task = Task.objects.create(owner=user, title="T", description="Short")
        monkeypatch.setattr("apps.ai_assistant.llm.chat", lambda *a, **k: None)
        result = improve_description(task)
        assert result["source"] == "heuristic"
        assert any("muy corta" in s for s in result["suggestions"])

    def test_llm_not_configured(self, settings, user):
        settings.AI_LLM_BASE_URL = ""
        task = Task.objects.create(owner=user, title="T", description="Short")
        result = improve_description(task)
        assert result["source"] == "heuristic"
