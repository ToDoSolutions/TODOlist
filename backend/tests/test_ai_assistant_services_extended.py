"""Tests exhaustivos para ai_assistant/services.py."""
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.ai_assistant.services import (
    _days_until_due,
    detect_blockers,
    estimate_priority,
    estimate_story_points,
    improve_description,
)
from apps.projects.models import Project
from apps.tasks.models import Task, TaskRelation

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="ais", email="ais@ais.com", password="pass")


@pytest.fixture
def project(user, db):
    return Project.objects.create(owner=user, name="Test Project")


@pytest.mark.django_db
class TestDaysUntilDue:
    def test_no_due_date(self, user, project):
        task = Task.objects.create(owner=user, project=project, title="No due")
        assert _days_until_due(task) is None

    def test_future_due(self, user, project):
        task = Task.objects.create(
            owner=user, project=project, title="Future",
            due_date=timezone.now() + timedelta(days=3)
        )
        days = _days_until_due(task)
        assert days is not None
        assert 2.9 < days < 3.1

    def test_past_due(self, user, project):
        task = Task.objects.create(
            owner=user, project=project, title="Past",
            due_date=timezone.now() - timedelta(days=2)
        )
        days = _days_until_due(task)
        assert days is not None
        assert days < 0


@pytest.mark.django_db
class TestEstimatePriority:
    def test_completed_task(self, user, project):
        task = Task.objects.create(owner=user, project=project, title="Done", state="completed")
        result = estimate_priority(task)
        assert result["suggested_priority"] == 5
        assert "tarea inactiva" in result["reasons"]

    def test_overdue_task(self, user, project):
        task = Task.objects.create(
            owner=user, project=project, title="Overdue",
            due_date=timezone.now() - timedelta(days=1), priority=3
        )
        result = estimate_priority(task)
        assert result["suggested_priority"] <= 2
        assert "tarea vencida" in result["reasons"]

    def test_due_soon(self, user, project):
        task = Task.objects.create(
            owner=user, project=project, title="Due soon",
            due_date=timezone.now() + timedelta(hours=12), priority=3
        )
        result = estimate_priority(task)
        assert "vence en menos de 1 día" in result["reasons"]

    def test_blocked_task(self, user, project):
        task = Task.objects.create(owner=user, project=project, title="Blocked", state="blocked")
        result = estimate_priority(task)
        assert "bloqueada" in result["reasons"]

    def test_blocks_others(self, user, project):
        task1 = Task.objects.create(owner=user, project=project, title="Blocker")
        task2 = Task.objects.create(owner=user, project=project, title="Blocked")
        TaskRelation.objects.create(source=task1, target=task2, relation_type="blocks")
        result = estimate_priority(task1)
        assert any("bloquea" in r for r in result["reasons"])

    def test_no_signals(self, user, project):
        task = Task.objects.create(owner=user, project=project, title="Normal", priority=3)
        result = estimate_priority(task)
        assert result["suggested_priority"] >= 3


@pytest.mark.django_db
class TestEstimateStoryPoints:
    def test_no_description(self, user, project):
        task = Task.objects.create(owner=user, project=project, title="No desc")
        result = estimate_story_points(task)
        assert "sin descripción" in result["reasons"]
        assert result["suggested_points"] == 1

    def test_long_description(self, user, project):
        task = Task.objects.create(
            owner=user, project=project, title="Long desc",
            description="x" * 600
        )
        result = estimate_story_points(task)
        assert "descripción extensa" in result["reasons"]

    def test_many_subtasks(self, user, project):
        from apps.tasks.models import Subtask
        task = Task.objects.create(owner=user, project=project, title="Many subtasks")
        for i in range(7):
            Subtask.objects.create(task=task, title=f"Sub {i}")
        result = estimate_story_points(task)
        assert any("subtareas" in r for r in result["reasons"])

    def test_depends_on(self, user, project):
        task1 = Task.objects.create(owner=user, project=project, title="Depends")
        task2 = Task.objects.create(owner=user, project=project, title="Depended")
        TaskRelation.objects.create(source=task1, target=task2, relation_type="depends_on")
        result = estimate_story_points(task1)
        assert any("depende de" in r for r in result["reasons"])


@pytest.mark.django_db
class TestDetectBlockers:
    def test_no_blockers(self, user):
        result = detect_blockers(user)
        assert result == []

    def test_stale_in_progress(self, user, project):
        task = Task.objects.create(
            owner=user, project=project, title="Stale", state="in_progress"
        )
        # Usar update() para evitar auto_now en updated_at
        Task.objects.filter(id=task.id).update(
            updated_at=timezone.now() - timedelta(days=10)
        )
        task.refresh_from_db()
        result = detect_blockers(user)
        assert len(result) == 1
        assert result[0]["blocker_type"] == "stale_in_progress"

    def test_dependency_unresolved(self, user, project):
        task1 = Task.objects.create(owner=user, project=project, title="Depends", state="pending")
        task2 = Task.objects.create(owner=user, project=project, title="Depended", state="pending")
        TaskRelation.objects.create(source=task1, target=task2, relation_type="depends_on")
        result = detect_blockers(user)
        assert len(result) == 1
        assert result[0]["blocker_type"] == "dependency_unresolved"

    def test_overdue(self, user, project):
        Task.objects.create(
            owner=user, project=project, title="Overdue", state="pending",
            due_date=timezone.now() - timedelta(days=5)
        )
        result = detect_blockers(user)
        assert len(result) == 1
        assert result[0]["blocker_type"] == "overdue"
        assert result[0]["severity"] == "high"


@pytest.mark.django_db
class TestImproveDescription:
    def test_no_description(self, user, project):
        task = Task.objects.create(owner=user, project=project, title="No desc")
        result = improve_description(task)
        assert "La tarea no tiene descripción" in result["suggestions"][0]

    def test_short_description(self, user, project):
        task = Task.objects.create(
            owner=user, project=project, title="Short",
            description="Fix bug"
        )
        result = improve_description(task)
        assert any("muy corta" in s for s in result["suggestions"])

    def test_missing_context(self, user, project):
        task = Task.objects.create(
            owner=user, project=project, title="Missing ctx",
            description="A" * 300
        )
        result = improve_description(task)
        assert any("cómo" in s or "how" in s for s in result["suggestions"])
        assert any("por qué" in s or "why" in s for s in result["suggestions"])
        assert any("criterios" in s or "acceptance" in s for s in result["suggestions"])

    def test_complete_description(self, user, project):
        task = Task.objects.create(
            owner=user, project=project, title="Complete",
            description="Cómo hacer la tarea. Por qué es importante. Criterios de aceptación." * 10
        )
        result = improve_description(task)
        assert "completa" in result["suggestions"][0] or "formato" in result["suggestions"][0]
