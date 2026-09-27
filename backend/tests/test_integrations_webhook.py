from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.integrations.models import (
    GitHubCheckRun,
    GitHubInstallation,
    GitHubPullRequest,
    GitHubRelease,
    GitHubRepo,
    WebhookDelivery,
)
from apps.integrations.webhook_processor import (
    _dispatch_event,
    process_pending_retries,
    process_webhook_delivery,
    retry_dead_letter_deliveries,
)

User = get_user_model()


@pytest.mark.django_db
class TestProcessWebhookDelivery:
    @pytest.fixture(autouse=True)
    def setup_data(self, db):
        self.user = User.objects.create_user(username="w", email="w@w.com", password="pass")

    def test_new_delivery_processed(self):
        with patch("apps.integrations.webhook_processor._dispatch_event") as mock_dispatch:
            mock_dispatch.return_value = {"message": "ok"}
            result, status = process_webhook_delivery("d1", "issues", "opened", {})
            assert status == 200
            assert result["message"] == "ok"
            delivery = WebhookDelivery.objects.get(delivery_id="d1")
            assert delivery.status == WebhookDelivery.Status.PROCESSED

    def test_already_processed(self):
        WebhookDelivery.objects.create(delivery_id="d2", status=WebhookDelivery.Status.PROCESSED)
        result, status = process_webhook_delivery("d2", "issues", "opened", {})
        assert status == 200
        assert "ya procesado" in result["message"]

    def test_dead_letter(self):
        WebhookDelivery.objects.create(delivery_id="d3", status=WebhookDelivery.Status.DEAD_LETTER)
        result, status = process_webhook_delivery("d3", "issues", "opened", {})
        assert status == 200
        assert "DLQ" in result["message"]

    def test_error_retry(self):
        with patch("apps.integrations.webhook_processor._dispatch_event") as mock_dispatch:
            mock_dispatch.side_effect = Exception("fail")
            result, status = process_webhook_delivery("d4", "issues", "opened", {})
            assert status == 500
            assert result["retry_count"] == 1
            delivery = WebhookDelivery.objects.get(delivery_id="d4")
            assert delivery.status == WebhookDelivery.Status.RETRYING
            assert delivery.next_retry_at is not None

    def test_error_dead_letter(self):
        delivery = WebhookDelivery.objects.create(delivery_id="d5", retry_count=5, max_retries=5)
        with patch("apps.integrations.webhook_processor._dispatch_event") as mock_dispatch:
            mock_dispatch.side_effect = Exception("fail")
            _, status = process_webhook_delivery("d5", "issues", "opened", {})
            assert status == 500
            delivery.refresh_from_db()
            assert delivery.status == WebhookDelivery.Status.DEAD_LETTER
            assert delivery.next_retry_at is None


@pytest.mark.django_db
class TestDispatchEvent:
    def test_unknown_event(self):
        result = _dispatch_event("unknown", "action", {})
        assert "no handler" in result["message"]

    def test_issue_event_no_data(self):
        result = _dispatch_event("issues", "opened", {})
        assert "Missing issue data" in result["message"]

    def test_issue_event_repo_not_tracked(self):
        result = _dispatch_event("issues", "opened", {"issue": {"number": 1}, "repository": {"full_name": "a/b"}})
        assert "not tracked" in result["message"]

    def test_issue_event_opened(self):
        GitHubRepo.objects.create(installation=GitHubInstallation.objects.create(user=User.objects.create_user(username="x", email="x@x.com", password="p"), installation_id=1), repo_id=1, full_name="a/b", name="b", owner="a")
        with patch("apps.integrations.sync_service.import_issue_as_task") as mock_import:
            result = _dispatch_event("issues", "opened", {"issue": {"number": 1}, "repository": {"full_name": "a/b"}})
            assert "imported" in result["message"]
            mock_import.assert_called_once()

    def test_pr_event(self):
        repo = GitHubRepo.objects.create(installation=GitHubInstallation.objects.create(user=User.objects.create_user(username="y", email="y@y.com", password="p"), installation_id=2), repo_id=2, full_name="a/b", name="b", owner="a")
        payload = {"pull_request": {"number": 1, "id": 100, "title": "PR", "state": "open"}, "repository": {"full_name": "a/b"}}
        result = _dispatch_event("pull_request", "opened", payload)
        assert "PR #1" in result["message"]
        assert GitHubPullRequest.objects.filter(repo=repo, pr_number=1).exists()

    def test_release_event(self):
        repo = GitHubRepo.objects.create(installation=GitHubInstallation.objects.create(user=User.objects.create_user(username="z", email="z@z.com", password="p"), installation_id=3), repo_id=3, full_name="a/b", name="b", owner="a")
        payload = {"release": {"id": 10, "tag_name": "v1.0", "name": "Release"}, "repository": {"full_name": "a/b"}}
        result = _dispatch_event("release", "published", payload)
        assert "Release v1.0" in result["message"]
        assert GitHubRelease.objects.filter(repo=repo, tag_name="v1.0").exists()

    def test_check_run_event(self):
        repo = GitHubRepo.objects.create(installation=GitHubInstallation.objects.create(user=User.objects.create_user(username="w2", email="w2@w.com", password="p"), installation_id=4), repo_id=4, full_name="a/b", name="b", owner="a")
        payload = {"check_run": {"id": 5, "name": "CI", "status": "completed", "conclusion": "success"}, "repository": {"full_name": "a/b"}}
        result = _dispatch_event("check_run", "completed", payload)
        assert "Check CI" in result["message"]
        assert GitHubCheckRun.objects.filter(repo=repo, check_id=5).exists()


@pytest.mark.django_db
class TestRetryFunctions:
    def test_retry_dead_letter(self):
        delivery = WebhookDelivery.objects.create(delivery_id="dlq1", status=WebhookDelivery.Status.DEAD_LETTER, retry_count=5, error_message="err")
        with patch("apps.integrations.tasks.process_webhook_retry_task.delay") as mock_delay:
            result = retry_dead_letter_deliveries()
            assert "1" in result
            delivery.refresh_from_db()
            assert delivery.status == WebhookDelivery.Status.PENDING
            assert delivery.retry_count == 0
            assert delivery.error_message == ""
            mock_delay.assert_called_once_with(delivery.id)

    def test_process_pending_retries(self):
        past = timezone.now() - timezone.timedelta(seconds=10)
        delivery = WebhookDelivery.objects.create(delivery_id="retry1", status=WebhookDelivery.Status.RETRYING, next_retry_at=past)
        with patch("apps.integrations.tasks.process_webhook_retry_task.delay") as mock_delay:
            result = process_pending_retries()
            assert "1" in result
            mock_delay.assert_called_once_with(delivery.id)

    def test_process_pending_retries_none(self):
        future = timezone.now() + timezone.timedelta(seconds=10)
        WebhookDelivery.objects.create(delivery_id="retry2", status=WebhookDelivery.Status.RETRYING, next_retry_at=future)
        result = process_pending_retries()
        assert "0" in result
