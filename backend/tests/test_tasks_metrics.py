"""Tests exhaustivos para tasks/metrics.py."""
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.projects.models import Project
from apps.tasks.metrics import (
    _days_between,
    _hours_between,
    _percentile,
    get_backlog_health,
    get_dashboard_summary,
    get_flow_metrics,
    get_pr_metrics,
    get_sprint_metrics,
)
from apps.tasks.models import Sprint, Task

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="met", email="met@met.com", password="pass")


@pytest.fixture
def project(user, db):
    return Project.objects.create(owner=user, name="Test Project")


@pytest.mark.django_db
class TestHelpers:
    def test_percentile_empty(self):
        assert _percentile([], 50) == 0

    def test_percentile_single(self):
        assert _percentile([5], 50) == 5

    def test_percentile_multiple(self):
        assert _percentile([1, 2, 3, 4, 5], 50) == 3
        assert _percentile([1, 2, 3, 4, 5], 90) == 4.6

    def test_hours_between(self):
        now = timezone.now()
        later = now + timedelta(hours=2)
        assert _hours_between(now, later) == 2.0
        assert _hours_between(None, later) == 0
        assert _hours_between(now, None) == 0

    def test_days_between(self):
        now = timezone.now()
        later = now + timedelta(days=2)
        assert _days_between(now, later) == 2.0


@pytest.mark.django_db
class TestGetFlowMetrics:
    def test_empty(self, user):
        result = get_flow_metrics(user, days=30)
        assert result["throughput"] == 0
        assert result["wip"] == 0
        assert result["backlog"] == 0
        assert result["blocked"] == 0
        assert result["overdue"] == 0

    def test_completed_tasks(self, user, project):
        Task.objects.create(
            owner=user, project=project, title="Done",
            state="completed", completed_at=timezone.now()
        )
        result = get_flow_metrics(user, days=30)
        assert result["throughput"] == 1
        assert result["lead_time"]["count"] == 1

    def test_wip_tasks(self, user, project):
        Task.objects.create(owner=user, project=project, title="WIP", state="in_progress")
        result = get_flow_metrics(user, days=30)
        assert result["wip"] == 1

    def test_overdue_tasks(self, user, project):
        Task.objects.create(
            owner=user, project=project, title="Overdue",
            state="pending", due_date=timezone.now() - timedelta(days=1)
        )
        result = get_flow_metrics(user, days=30)
        assert result["overdue"] == 1


@pytest.mark.django_db
class TestGetBacklogHealth:
    def test_empty(self, user):
        result = get_backlog_health(user)
        assert result["total_open"] == 0
        assert result["health_score"] == 100

    def test_no_estimate(self, user, project):
        Task.objects.create(owner=user, project=project, title="No est", state="pending")
        result = get_backlog_health(user)
        assert result["no_estimate"] == 1


@pytest.mark.django_db
class TestGetSprintMetrics:
    def test_sprint_not_found(self, user):
        result = get_sprint_metrics(user, 999)
        assert result is None

    def test_sprint_metrics(self, user, project):
        sprint = Sprint.objects.create(
            owner=user, project=project, name="Sprint 1", state="active",
            start_date=timezone.now().date(), end_date=timezone.now().date() + timedelta(days=14)
        )
        Task.objects.create(owner=user, project=project, title="Task 1", sprint=sprint, state="completed")
        Task.objects.create(owner=user, project=project, title="Task 2", sprint=sprint, state="in_progress")
        result = get_sprint_metrics(user, sprint.id)
        assert result["sprint_name"] == "Sprint 1"
        assert result["total_tasks"] == 2
        assert result["done"] == 1
        assert result["in_progress"] == 1
        assert result["progress_pct"] == 50.0


@pytest.mark.django_db
class TestGetDashboardSummary:
    def test_empty(self, user):
        result = get_dashboard_summary(user)
        assert result["open"] == 0
        assert result["completed"] == 0
        assert result["overdue"] == 0
        assert result["blocked"] == 0

    def test_counts(self, user, project):
        Task.objects.create(owner=user, project=project, title="Open", state="pending")
        Task.objects.create(owner=user, project=project, title="Done", state="completed")
        Task.objects.create(owner=user, project=project, title="Blocked", state="blocked")
        result = get_dashboard_summary(user)
        assert result["open"] == 2  # pending + blocked
        assert result["completed"] == 1
        assert result["blocked"] == 1


@pytest.mark.django_db
class TestGetPrMetrics:
    def test_empty(self, user):
        result = get_pr_metrics(user)
        assert result["total"] == 0
        assert result["open"] == 0
        assert result["merged"] == 0
