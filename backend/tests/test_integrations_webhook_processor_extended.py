"""Tests exhaustivos para integrations/webhook_processor.py."""
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.integrations.models import GitHubInstallation, GitHubRepo, WebhookDelivery
from apps.integrations.webhook_processor import (
    _dispatch_event,
    _handle_issue_event,
    _handle_pr_event,
    process_pending_retries,
    process_webhook_delivery,
    retry_dead_letter_deliveries,
)

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="wp", email="wp@wp.com", password="pass")


@pytest.fixture
def installation(user, db):
    return GitHubInstallation.objects.create(user=user, installation_id=123)


@pytest.fixture
def repo(installation, db):
    return GitHubRepo.objects.create(
        installation=installation, repo_id=456, full_name="org/repo", name="repo", owner="org"
    )


@pytest.mark.django_db
class TestProcessWebhookDelivery:
    def test_creates_delivery(self):
        _, status = process_webhook_delivery("d-1", "issues", "opened", {})
        assert status == 200
        assert WebhookDelivery.objects.filter(delivery_id="d-1").exists()

    def test_idempotent(self):
        process_webhook_delivery("d-1", "issues", "opened", {})
        data, status = process_webhook_delivery("d-1", "issues", "opened", {})
        assert status == 200
        assert "ya procesado" in data["message"]

    def test_dead_letter(self):
        WebhookDelivery.objects.create(
            delivery_id="d-1", event_type="issues", action="opened",
            payload={}, status="dead_letter"
        )
        data, _ = process_webhook_delivery("d-1", "issues", "opened", {})
        assert "DLQ" in data["message"]

    def test_retry_on_error(self):
        with patch("apps.integrations.webhook_processor._dispatch_event", side_effect=Exception("fail")):
            data, status = process_webhook_delivery("d-1", "issues", "opened", {})
            assert status == 500
            assert data["retry_count"] == 1

    def test_dead_letter_after_max_retries(self):
        WebhookDelivery.objects.create(
            delivery_id="d-1", event_type="issues", action="opened",
            payload={}, status="pending", retry_count=4, max_retries=5
        )
        with patch("apps.integrations.webhook_processor._dispatch_event", side_effect=Exception("fail")):
            process_webhook_delivery("d-1", "issues", "opened", {})
            delivery = WebhookDelivery.objects.get(delivery_id="d-1")
            assert delivery.status == "dead_letter"


@pytest.mark.django_db
class TestDispatchEvent:
    def test_issues(self, repo):
        result = _dispatch_event("issues", "opened", {
            "issue": {"id": 1, "number": 1, "title": "Bug", "state": "open"},
            "repository": {"full_name": "org/repo"},
        })
        assert "imported" in result["message"] or "no handler" in result["message"]

    def test_installation_repos_added(self, repo):
        result = _dispatch_event("installation_repositories", "added", {
            "installation": {"id": 123},
            "repositories_added": [{"id": 789, "full_name": "org/new", "name": "new"}],
        })
        assert "Installation repos added" in result["message"]

    def test_installation_deleted(self, installation):
        result = _dispatch_event("installation", "deleted", {"installation": {"id": 123}})
        assert "Installation deleted" in result["message"]
        assert not GitHubInstallation.objects.filter(installation_id=123).exists()

    def test_pull_request(self, repo):
        result = _dispatch_event("pull_request", "opened", {
            "pull_request": {"number": 1, "title": "PR", "state": "open"},
            "repository": {"full_name": "org/repo"},
        })
        assert "PR #1" in result["message"]

    def test_release(self, repo):
        result = _dispatch_event("release", "published", {
            "release": {"tag_name": "v1.0", "id": 1},
            "repository": {"full_name": "org/repo"},
        })
        assert "Release v1.0" in result["message"]

    def test_check_run(self, repo):
        result = _dispatch_event("check_run", "completed", {
            "check_run": {"id": 1, "name": "CI", "status": "completed"},
            "repository": {"full_name": "org/repo"},
        })
        assert "Check CI" in result["message"]

    def test_unknown_event(self):
        result = _dispatch_event("unknown", "action", {})
        assert "no handler" in result["message"]


@pytest.mark.django_db
class TestHandleIssueEvent:
    def test_missing_issue_data(self):
        result = _handle_issue_event("opened", {})
        assert "Missing issue data" in result["message"]

    def test_repo_not_tracked(self):
        result = _handle_issue_event("opened", {
            "issue": {"number": 1},
            "repository": {"full_name": "unknown/repo"},
        })
        assert "not tracked" in result["message"]

    def test_opened_no_link(self, repo):
        result = _handle_issue_event("opened", {
            "issue": {"id": 1, "number": 1, "title": "Bug", "state": "open"},
            "repository": {"full_name": "org/repo"},
        })
        assert "imported" in result["message"]


@pytest.mark.django_db
class TestHandlePrEvent:
    def test_missing_pr_data(self):
        result = _handle_pr_event("opened", {})
        assert "Missing PR data" in result["message"]

    def test_repo_not_tracked(self):
        result = _handle_pr_event("opened", {
            "pull_request": {"number": 1},
            "repository": {"full_name": "unknown/repo"},
        })
        assert "not tracked" in result["message"]


@pytest.mark.django_db
class TestRetryDeadLetter:
    def test_retry_dead_letter(self):
        WebhookDelivery.objects.create(
            delivery_id="d-1", event_type="issues", action="opened",
            payload={}, status="dead_letter", repo_full_name="org/repo"
        )
        with patch("apps.integrations.tasks.process_webhook_retry_task"):
            result = retry_dead_letter_deliveries(repo_full_name="org/repo")
            assert "Reintentando 1" in result
            delivery = WebhookDelivery.objects.get(delivery_id="d-1")
            assert delivery.status == "pending"
            assert delivery.retry_count == 0

    def test_retry_filtered_by_repo(self):
        WebhookDelivery.objects.create(
            delivery_id="d-1", event_type="issues", action="opened",
            payload={}, status="dead_letter", repo_full_name="org/repo"
        )
        WebhookDelivery.objects.create(
            delivery_id="d-2", event_type="issues", action="opened",
            payload={}, status="dead_letter", repo_full_name="other/repo"
        )
        with patch("apps.integrations.tasks.process_webhook_retry_task"):
            retry_dead_letter_deliveries(repo_full_name="org/repo")
            assert WebhookDelivery.objects.get(delivery_id="d-1").status == "pending"
            assert WebhookDelivery.objects.get(delivery_id="d-2").status == "dead_letter"


@pytest.mark.django_db
class TestProcessPendingRetries:
    def test_no_pending(self):
        result = process_pending_retries()
        assert "Encolados 0" in result

    def test_pending_retries(self):
        WebhookDelivery.objects.create(
            delivery_id="d-1", event_type="issues", action="opened",
            payload={}, status="retrying",
            next_retry_at=timezone.now() - timezone.timedelta(minutes=1)
        )
        with patch("apps.integrations.tasks.process_webhook_retry_task"):
            result = process_pending_retries()
            assert "Encolados 1" in result
