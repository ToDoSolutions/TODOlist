from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model

from apps.integrations.models import GitHubInstallation, GitHubRepo, WebhookDelivery
from apps.integrations.tasks import (
    process_pending_webhook_retries,
    process_webhook_retry_task,
    sync_all_github_issues,
    sync_all_github_repos_data,
    sync_repo_issues_task,
)

User = get_user_model()


@pytest.mark.django_db
class TestSyncRepoIssuesTask:
    def test_sync_repo(self):
        user = User.objects.create_user(username="it", email="it@it.com", password="pass")
        inst = GitHubInstallation.objects.create(user=user, installation_id=1)
        repo = GitHubRepo.objects.create(installation=inst, repo_id=1, full_name="a/b", name="b", owner="a", sync_enabled=True)
        with patch("apps.integrations.tasks.sync_repo_issues", return_value=5):
            result = sync_repo_issues_task(repo.id)
            assert "Synced 5 issues" in result

    def test_sync_repo_disabled(self):
        user = User.objects.create_user(username="it2", email="it2@it.com", password="pass")
        inst = GitHubInstallation.objects.create(user=user, installation_id=1)
        repo = GitHubRepo.objects.create(installation=inst, repo_id=1, full_name="a/b", name="b", owner="a", sync_enabled=False)
        result = sync_repo_issues_task(repo.id)
        assert "sync disabled" in result

    def test_sync_repo_not_found(self):
        result = sync_repo_issues_task(999)
        assert "not found" in result


@pytest.mark.django_db
class TestSyncAllGithubIssues:
    def test_queue_sync(self):
        user = User.objects.create_user(username="it3", email="it3@it.com", password="pass")
        inst = GitHubInstallation.objects.create(user=user, installation_id=1)
        GitHubRepo.objects.create(installation=inst, repo_id=1, full_name="a/b", name="b", owner="a", sync_enabled=True)
        GitHubRepo.objects.create(installation=inst, repo_id=2, full_name="a/c", name="c", owner="a", sync_enabled=True)
        with patch("apps.integrations.tasks.sync_repo_issues_task") as mock_task:
            result = sync_all_github_issues()
            assert result == "Queued sync for 2 repos"
            assert mock_task.delay.call_count == 2


@pytest.mark.django_db
class TestProcessWebhookRetryTask:
    def test_retry(self):
        delivery = WebhookDelivery.objects.create(
            delivery_id="d1", event_type="issues", action="opened",
            repo_full_name="a/b", payload={}, status="failed",
        )
        with patch("apps.integrations.webhook_processor.process_webhook_delivery", return_value=({"status": "ok"}, 200)):
            result = process_webhook_retry_task(delivery.id)
            assert "Retry delivery" in result

    def test_retry_already_processed(self):
        delivery = WebhookDelivery.objects.create(
            delivery_id="d1", event_type="issues", action="opened",
            repo_full_name="a/b", payload={}, status="processed",
        )
        result = process_webhook_retry_task(delivery.id)
        assert "already processed" in result

    def test_retry_not_found(self):
        result = process_webhook_retry_task(999)
        assert "not found" in result


@pytest.mark.django_db
class TestProcessPendingWebhookRetries:
    def test_process_pending(self):
        with patch("apps.integrations.webhook_processor.process_pending_retries", return_value="processed"):
            result = process_pending_webhook_retries()
            assert result == "processed"


@pytest.mark.django_db
class TestSyncAllGithubReposData:
    def test_sync_all(self):
        user = User.objects.create_user(username="it4", email="it4@it.com", password="pass")
        inst = GitHubInstallation.objects.create(user=user, installation_id=1)
        GitHubRepo.objects.create(installation=inst, repo_id=1, full_name="a/b", name="b", owner="a", sync_enabled=True)
        GitHubRepo.objects.create(installation=inst, repo_id=2, full_name="a/c", name="c", owner="a", sync_enabled=True)
        with patch("apps.integrations.tasks.sync_repo_data", return_value={"pull_requests": 1, "commits": 2, "releases": 3, "check_runs": 4}):
            result = sync_all_github_repos_data()
            assert result["repos"] == 2
            assert result["errors"] == 0
            assert result["synced"]["pull_requests"] == 2

    def test_sync_all_error(self):
        user = User.objects.create_user(username="it5", email="it5@it.com", password="pass")
        inst = GitHubInstallation.objects.create(user=user, installation_id=1)
        GitHubRepo.objects.create(installation=inst, repo_id=1, full_name="a/b", name="b", owner="a", sync_enabled=True)
        with patch("apps.integrations.tasks.sync_repo_data", side_effect=Exception("error")):
            result = sync_all_github_repos_data()
            assert result["repos"] == 1
            assert result["errors"] == 1
