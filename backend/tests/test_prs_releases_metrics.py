"""Tests de Fase 6 (PRs, releases, CI) y Fase 7 (métricas)."""
import json
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.integrations.models import (
    GitHubCheckRun,
    GitHubInstallation,
    GitHubIssueLink,
    GitHubPullRequest,
    GitHubRelease,
    GitHubRepo,
)
from apps.tasks.models import Sprint, Task


@pytest.fixture
def github_installation(user):
    return GitHubInstallation.objects.create(
        user=user, installation_id=12345, account_login="testuser",
        github_user_id=67890, github_username="testuser",
        access_token="gho_test",
    )


@pytest.fixture
def github_repo(github_installation):
    return GitHubRepo.objects.create(
        installation=github_installation, repo_id=100,
        full_name="testuser/my-repo", name="my-repo", owner="testuser",
    )


# --- Fase 6: PRs, Releases, CI ---

@pytest.mark.django_db
class TestPullRequests:
    def test_crear_pr_desde_webhook(self, api_client, github_repo):
        with patch("apps.integrations.views.GitHubAppClient.verify_webhook_signature", return_value=True):
            payload = {
                "action": "opened",
                "pull_request": {
                    "id": 9001, "number": 42, "title": "Fix bug",
                    "state": "open", "merged": False, "draft": False,
                    "html_url": "https://github.com/testuser/my-repo/pull/42",
                    "head": {"ref": "fix-bug"}, "base": {"ref": "main"},
                    "user": {"login": "dev1"},
                    "created_at": timezone.now().isoformat(),
                    "review_comments": 0,
                },
                "repository": {"full_name": "testuser/my-repo"},
            }
            resp = api_client.post(
                "/api/webhooks/github/", data=json.dumps(payload),
                content_type="application/json",
                HTTP_X_GITHUB_EVENT="pull_request",
                HTTP_X_GITHUB_DELIVERY="delivery-pr-001",
            )
        assert resp.status_code == 200
        assert GitHubPullRequest.objects.filter(pr_number=42).exists()

    def test_vincular_pr_a_tarea(self, authed_client, github_repo, user):
        pr = GitHubPullRequest.objects.create(
            repo=github_repo, pr_number=10, pr_id=100,
            title="PR test", state="open",
            html_url="https://github.com/testuser/my-repo/pull/10",
        )
        task = Task.objects.create(owner=user, title="Tarea")
        resp = authed_client.post(
            f"/api/github/prs/{pr.id}/link_task/",
            {"task_id": task.id},
            format="json",
        )
        assert resp.status_code == 200
        assert pr.tasks.filter(id=task.id).exists()

    def test_listar_prs(self, authed_client, github_repo):
        GitHubPullRequest.objects.create(
            repo=github_repo, pr_number=1, pr_id=1,
            title="PR 1", state="open", html_url="http://example.com/1",
        )
        resp = authed_client.get("/api/github/prs/")
        assert resp.status_code == 200
        data = resp.data.get("results", resp.data) if isinstance(resp.data, dict) else resp.data
        assert len(data) == 1

    def test_pr_detecta_tarea_por_referencia(self, api_client, github_repo, user):
        """Un PR que referencia #99 debe vincularse a la tarea con issue_number=99."""
        task = Task.objects.create(owner=user, title="Issue 99")
        GitHubIssueLink.objects.create(
            task=task, repo=github_repo, issue_number=99,
            issue_id=990, issue_url="http://example.com/99",
            issue_state="open",
        )
        with patch("apps.integrations.views.GitHubAppClient.verify_webhook_signature", return_value=True):
            payload = {
                "action": "opened",
                "pull_request": {
                    "id": 9002, "number": 50, "title": "Fix #99",
                    "state": "open", "merged": False,
                    "html_url": "https://github.com/testuser/my-repo/pull/50",
                    "head": {"ref": "fix"}, "base": {"ref": "main"},
                    "user": {"login": "dev1"},
                    "created_at": timezone.now().isoformat(),
                    "review_comments": 0,
                    "body": "This fixes #99",
                },
                "repository": {"full_name": "testuser/my-repo"},
            }
            api_client.post(
                "/api/webhooks/github/", data=json.dumps(payload),
                content_type="application/json",
                HTTP_X_GITHUB_EVENT="pull_request",
                HTTP_X_GITHUB_DELIVERY="delivery-pr-ref-001",
            )
        pr = GitHubPullRequest.objects.get(pr_number=50)
        assert pr.tasks.filter(id=task.id).exists()


@pytest.mark.django_db
class TestReleases:
    def test_crear_release_desde_webhook(self, api_client, github_repo):
        with patch("apps.integrations.views.GitHubAppClient.verify_webhook_signature", return_value=True):
            payload = {
                "action": "published",
                "release": {
                    "id": 8001, "tag_name": "v1.0.0", "name": "First release",
                    "body": "Changelog", "html_url": "https://github.com/testuser/my-repo/releases/v1.0.0",
                    "prerelease": False,
                    "author": {"login": "dev1"},
                    "published_at": timezone.now().isoformat(),
                },
                "repository": {"full_name": "testuser/my-repo"},
            }
            resp = api_client.post(
                "/api/webhooks/github/", data=json.dumps(payload),
                content_type="application/json",
                HTTP_X_GITHUB_EVENT="release",
                HTTP_X_GITHUB_DELIVERY="delivery-rel-001",
            )
        assert resp.status_code == 200
        assert GitHubRelease.objects.filter(tag_name="v1.0.0").exists()

    def test_progreso_release(self, authed_client, github_repo, user):
        release = GitHubRelease.objects.create(
            repo=github_repo, release_id=8001, tag_name="v2.0.0",
            html_url="http://example.com/v2",
        )
        t1 = Task.objects.create(owner=user, title="T1", state="completed")
        t2 = Task.objects.create(owner=user, title="T2", state="pending")
        release.tasks.add(t1, t2)
        resp = authed_client.get(f"/api/github/releases/{release.id}/progress/")
        assert resp.status_code == 200
        assert resp.data["tasks_total"] == 2
        assert resp.data["tasks_done"] == 1
        assert resp.data["progress_pct"] == 50.0


@pytest.mark.django_db
class TestCheckRuns:
    def test_crear_check_run_desde_webhook(self, api_client, github_repo):
        with patch("apps.integrations.views.GitHubAppClient.verify_webhook_signature", return_value=True):
            payload = {
                "action": "completed",
                "check_run": {
                    "id": 7001, "name": "CI", "status": "completed",
                    "conclusion": "success",
                    "html_url": "https://github.com/testuser/my-repo/runs/7001",
                    "started_at": timezone.now().isoformat(),
                    "completed_at": timezone.now().isoformat(),
                    "head_sha": "abc123",
                    "pull_requests": [],
                },
                "repository": {"full_name": "testuser/my-repo"},
            }
            resp = api_client.post(
                "/api/webhooks/github/", data=json.dumps(payload),
                content_type="application/json",
                HTTP_X_GITHUB_EVENT="check_run",
                HTTP_X_GITHUB_DELIVERY="delivery-check-001",
            )
        assert resp.status_code == 200
        assert GitHubCheckRun.objects.filter(name="CI").exists()


# --- Fase 7: Métricas ---

@pytest.mark.django_db
class TestFlowMetrics:
    def test_metrics_flow_vacio(self, authed_client):
        resp = authed_client.get("/api/tasks/metrics_flow/")
        assert resp.status_code == 200
        assert resp.data["throughput"] == 0
        assert resp.data["wip"] == 0

    def test_metrics_flow_con_tareas(self, authed_client, user):
        # Crear tarea completada
        t1 = Task.objects.create(owner=user, title="T1", state="completed")
        t1.completed_at = timezone.now()
        t1.save()
        # Crear tarea en progreso
        Task.objects.create(owner=user, title="T2", state="in_progress")

        resp = authed_client.get("/api/tasks/metrics_flow/")
        assert resp.status_code == 200
        assert resp.data["throughput"] == 1
        assert resp.data["wip"] == 1
        assert resp.data["lead_time"]["count"] == 1


@pytest.mark.django_db
class TestBacklogHealth:
    def test_backlog_health_vacio(self, authed_client):
        resp = authed_client.get("/api/tasks/metrics_backlog/")
        assert resp.status_code == 200
        assert resp.data["total_open"] == 0
        assert resp.data["health_score"] == 100

    def test_backlog_health_con_tareas(self, authed_client, user):
        Task.objects.create(owner=user, title="Sin estimar", state="pending")
        Task.objects.create(owner=user, title="Con SP", state="pending", story_points=5)
        resp = authed_client.get("/api/tasks/metrics_backlog/")
        assert resp.status_code == 200
        assert resp.data["total_open"] == 2
        assert resp.data["no_estimate"] == 1


@pytest.mark.django_db
class TestDashboardSummary:
    def test_dashboard_general(self, authed_client, user):
        Task.objects.create(owner=user, title="T1", state="pending")
        Task.objects.create(owner=user, title="T2", state="completed")
        Task.objects.create(owner=user, title="T3", state="in_progress", task_type="bug")

        resp = authed_client.get("/api/tasks/metrics_dashboard/")
        assert resp.status_code == 200
        assert resp.data["open"] == 2
        assert resp.data["completed"] == 1
        assert resp.data["by_state"]["pending"] == 1
        assert resp.data["by_state"]["completed"] == 1
        assert resp.data["by_type"]["bug"] == 1
        assert len(resp.data["backlog_trend"]) == 8

    def test_dashboard_con_sprint_activo(self, authed_client, user):
        sprint = Sprint.objects.create(
            owner=user, name="S1", state="active",
            start_date=timezone.localdate(), end_date=timezone.localdate() + timedelta(days=14),
        )
        Task.objects.create(owner=user, title="T1", state="completed", sprint=sprint)
        Task.objects.create(owner=user, title="T2", state="pending", sprint=sprint)

        resp = authed_client.get("/api/tasks/metrics_dashboard/")
        assert resp.status_code == 200
        assert resp.data["active_sprint"] is not None
        assert resp.data["active_sprint"]["total_tasks"] == 2
        assert resp.data["active_sprint"]["done"] == 1


@pytest.mark.django_db
class TestSprintMetrics:
    def test_metricas_sprint(self, authed_client, user):
        sprint = Sprint.objects.create(
            owner=user, name="S1", state="active",
            start_date=timezone.localdate(), end_date=timezone.localdate() + timedelta(days=14),
        )
        Task.objects.create(owner=user, title="T1", state="completed", sprint=sprint, story_points=5)
        Task.objects.create(owner=user, title="T2", state="in_progress", sprint=sprint, story_points=3)
        Task.objects.create(owner=user, title="T3", state="pending", sprint=sprint, story_points=2)

        resp = authed_client.get(f"/api/sprints/{sprint.id}/metrics/")
        assert resp.status_code == 200
        assert resp.data["total_tasks"] == 3
        assert resp.data["done"] == 1
        assert resp.data["story_points_total"] == 10
        assert resp.data["story_points_done"] == 5
        assert resp.data["progress_pct"] == 33.3

    def test_metricas_sprint_no_existe(self, authed_client):
        resp = authed_client.get("/api/sprints/9999/metrics/")
        assert resp.status_code == 404


@pytest.mark.django_db
class TestPRMetrics:
    def test_metricas_prs_vacio(self, authed_client):
        resp = authed_client.get("/api/tasks/metrics_prs/")
        assert resp.status_code == 200
        assert resp.data["total"] == 0

    def test_metricas_prs_con_datos(self, authed_client, github_repo):
        GitHubPullRequest.objects.create(
            repo=github_repo, pr_number=1, pr_id=1, title="PR1",
            state="open", html_url="http://example.com/1",
            created_at_gh=timezone.now() - timedelta(days=10),
        )
        GitHubPullRequest.objects.create(
            repo=github_repo, pr_number=2, pr_id=2, title="PR2",
            state="closed", is_merged=True, html_url="http://example.com/2",
            created_at_gh=timezone.now() - timedelta(days=5),
            merged_at=timezone.now() - timedelta(days=1),
        )
        resp = authed_client.get("/api/tasks/metrics_prs/")
        assert resp.status_code == 200
        assert resp.data["total"] == 2
        assert resp.data["open"] == 1
        assert resp.data["merged"] == 1
        assert resp.data["stale_7d"] == 1
        assert resp.data["merge_time"]["count"] == 1
