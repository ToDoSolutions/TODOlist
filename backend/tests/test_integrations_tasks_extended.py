"""Tests exhaustivos para integrations/tasks.py y sync_github.py."""
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model

from apps.integrations.models import (
    GitHubCheckRun,
    GitHubCommit,
    GitHubInstallation,
    GitHubPullRequest,
    GitHubRelease,
    GitHubRepo,
    WebhookDelivery,
)
from apps.integrations.sync_github import (
    _parse_iso,
    sync_check_runs,
    sync_commits,
    sync_pull_requests,
    sync_releases,
    sync_repo_data,
)
from apps.integrations.tasks import (
    process_webhook_retry_task,
    sync_all_github_issues,
    sync_all_github_repos_data,
    sync_repo_issues_task,
)

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="it", email="it@it.com", password="pass")


@pytest.fixture
def installation(user, db):
    return GitHubInstallation.objects.create(user=user, installation_id=123)


@pytest.fixture
def repo(installation, db):
    return GitHubRepo.objects.create(
        installation=installation, repo_id=456, full_name="org/repo",
        name="repo", owner="org", sync_enabled=True
    )


@pytest.mark.django_db
class TestSyncRepoIssuesTask:
    def test_repo_not_found(self):
        result = sync_repo_issues_task(999)
        assert "not found" in result

    def test_sync_disabled(self, repo):
        repo.sync_enabled = False
        repo.save()
        result = sync_repo_issues_task(repo.id)
        assert "sync disabled" in result

    def test_syncs_issues(self, repo):
        with patch("apps.integrations.tasks.sync_repo_issues", return_value=5):
            result = sync_repo_issues_task(repo.id)
            assert "Synced 5" in result


@pytest.mark.django_db
class TestSyncAllGitHubIssues:
    def test_queues_sync(self, repo):
        with patch("apps.integrations.tasks.sync_repo_issues_task"):
            result = sync_all_github_issues()
            assert "Queued sync for 1" in result


@pytest.mark.django_db
class TestProcessWebhookRetryTask:
    def test_delivery_not_found(self):
        result = process_webhook_retry_task(999)
        assert "not found" in result

    def test_already_processed(self):
        delivery = WebhookDelivery.objects.create(
            delivery_id="d-1", event_type="issues", action="opened",
            payload={}, status="processed"
        )
        result = process_webhook_retry_task(delivery.id)
        assert "already processed" in result


@pytest.mark.django_db
class TestSyncAllGitHubReposData:
    def test_syncs_all(self, repo):
        with patch("apps.integrations.tasks.sync_repo_data", return_value={
            "pull_requests": 1, "commits": 2, "releases": 3, "check_runs": 4
        }):
            result = sync_all_github_repos_data()
            assert result["repos"] == 1
            assert result["synced"]["pull_requests"] == 1

    def test_handles_errors(self, repo):
        with patch("apps.integrations.tasks.sync_repo_data", side_effect=Exception("fail")):
            result = sync_all_github_repos_data()
            assert result["errors"] == 1


@pytest.mark.django_db
class TestSyncGitHub:
    def test_parse_iso(self):
        assert _parse_iso("2024-01-01T00:00:00Z") is not None
        assert _parse_iso("") is None
        assert _parse_iso("invalid") is None

    def test_sync_pull_requests(self, repo, installation):
        mock_client = MagicMock()
        mock_client.list_pull_requests.return_value = [
            {"id": 1, "number": 1, "title": "PR", "state": "open"}
        ]
        with patch("apps.integrations.sync_github.GitHubAppClient", return_value=mock_client):
            synced = sync_pull_requests(repo, installation)
            assert synced == 1
            assert GitHubPullRequest.objects.filter(repo=repo, pr_number=1).exists()

    def test_sync_commits(self, repo, installation):
        mock_client = MagicMock()
        mock_client.list_commits.return_value = [
            {"sha": "abc123", "commit": {"message": "Fix", "author": {"name": "Dev"}}}
        ]
        with patch("apps.integrations.sync_github.GitHubAppClient", return_value=mock_client):
            synced = sync_commits(repo, installation)
            assert synced == 1
            assert GitHubCommit.objects.filter(sha="abc123").exists()

    def test_sync_releases(self, repo, installation):
        mock_client = MagicMock()
        mock_client.list_releases.return_value = [
            {"id": 1, "tag_name": "v1.0", "name": "Release"}
        ]
        with patch("apps.integrations.sync_github.GitHubAppClient", return_value=mock_client):
            synced = sync_releases(repo, installation)
            assert synced == 1
            assert GitHubRelease.objects.filter(release_id=1).exists()

    def test_sync_check_runs(self, repo, installation):
        mock_client = MagicMock()
        mock_client.list_check_runs.return_value = [
            {"id": 1, "name": "CI", "status": "completed", "conclusion": "success"}
        ]
        with patch("apps.integrations.sync_github.GitHubAppClient", return_value=mock_client):
            synced = sync_check_runs(repo, installation)
            assert synced == 1
            assert GitHubCheckRun.objects.filter(check_id=1).exists()

    def test_sync_repo_data(self, repo):
        with (
            patch("apps.integrations.sync_github.sync_pull_requests", return_value=1),
            patch("apps.integrations.sync_github.sync_commits", return_value=2),
            patch("apps.integrations.sync_github.sync_releases", return_value=3),
            patch("apps.integrations.sync_github.sync_check_runs", return_value=4),
        ):
            result = sync_repo_data(repo)
            assert result["pull_requests"] == 1
            assert result["commits"] == 2

    def test_sync_repo_data_disabled(self, repo):
        repo.sync_enabled = False
        repo.save()
        result = sync_repo_data(repo)
        assert result["pull_requests"] == 0
