"""Tests de idempotencia de webhooks y cola de reintentos."""
import json
import pytest
from unittest.mock import patch

from apps.integrations.models import (
    WebhookDelivery, GitHubRepo, GitHubIssueLink, GitHubInstallation,
)
from apps.tasks.models import Task
from apps.integrations.webhook_processor import (
    process_webhook_delivery,
    retry_dead_letter_deliveries,
)


@pytest.fixture
def github_installation(user):
    return GitHubInstallation.objects.create(
        user=user,
        installation_id=12345,
        account_login="testuser",
        account_type="User",
        github_user_id=67890,
        github_username="testuser",
        access_token="gho_test_token",
    )


@pytest.fixture
def github_repo(github_installation):
    return GitHubRepo.objects.create(
        installation=github_installation,
        repo_id=100,
        full_name="testuser/my-repo",
        name="my-repo",
        owner="testuser",
    )


@pytest.mark.django_db
class TestWebhookIdempotency:
    @patch("apps.integrations.views.GitHubAppClient.verify_webhook_signature", return_value=True)
    def test_webhook_procesado_primera_vez(self, mock_verify, api_client, github_repo, user):
        payload = {
            "action": "opened",
            "issue": {
                "id": 2001,
                "number": 99,
                "title": "Nuevo issue",
                "state": "open",
                "html_url": "https://github.com/testuser/my-repo/issues/99",
                "body": "",
            },
            "repository": {"full_name": "testuser/my-repo"},
        }
        resp = api_client.post(
            "/api/webhooks/github/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_GITHUB_EVENT="issues",
            HTTP_X_GITHUB_DELIVERY="delivery-001",
        )
        assert resp.status_code == 200
        assert "imported" in resp.data["message"]
        # Verificar que se registró
        delivery = WebhookDelivery.objects.get(delivery_id="delivery-001")
        assert delivery.status == "processed"

    @patch("apps.integrations.views.GitHubAppClient.verify_webhook_signature", return_value=True)
    def test_webhook_idempotente_no_reprocesa(self, mock_verify, api_client, github_repo, user):
        payload = {
            "action": "opened",
            "issue": {
                "id": 2001,
                "number": 100,
                "title": "Issue idempotente",
                "state": "open",
                "html_url": "https://github.com/testuser/my-repo/issues/100",
                "body": "",
            },
            "repository": {"full_name": "testuser/my-repo"},
        }
        # Primera entrega
        resp1 = api_client.post(
            "/api/webhooks/github/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_GITHUB_EVENT="issues",
            HTTP_X_GITHUB_DELIVERY="delivery-002",
        )
        assert resp1.status_code == 200
        tasks_before = Task.objects.filter(title="Issue idempotente").count()
        assert tasks_before == 1

        # Segunda entrega con mismo delivery_id → no debe duplicar
        resp2 = api_client.post(
            "/api/webhooks/github/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_GITHUB_EVENT="issues",
            HTTP_X_GITHUB_DELIVERY="delivery-002",
        )
        assert resp2.status_code == 200
        assert "ya procesado" in resp2.data["message"]
        tasks_after = Task.objects.filter(title="Issue idempotente").count()
        assert tasks_after == 1  # No se duplicó

    @patch("apps.integrations.webhook_processor._handle_issue_event")
    def test_webhook_falla_y_reintenta(self, mock_handler, github_repo):
        """Un webhook que falla debe registrarse para reintento."""
        mock_handler.side_effect = Exception("API de GitHub caída")

        result, status = process_webhook_delivery(
            delivery_id="delivery-fail-001",
            event_type="issues",
            action="closed",
            payload={"action": "closed", "issue": {"number": 1}, "repository": {"full_name": "testuser/my-repo"}},
            repo_full_name="testuser/my-repo",
        )

        assert status == 500
        delivery = WebhookDelivery.objects.get(delivery_id="delivery-fail-001")
        assert delivery.status == "retrying"
        assert delivery.retry_count == 1
        assert delivery.next_retry_at is not None
        assert "API de GitHub caída" in delivery.error_message

    @patch("apps.integrations.webhook_processor._handle_issue_event")
    def test_webhook_a_dlq_tras_max_reintentos(self, mock_handler):
        """Tras max_retries, el webhook va a la cola de mensajes fallidos (DLQ)."""
        mock_handler.side_effect = Exception("Error persistente")

        delivery_id = "delivery-dlq-001"
        # Simular que ya tiene max_retries - 1 intentos
        delivery = WebhookDelivery.objects.create(
            delivery_id=delivery_id,
            event_type="issues",
            action="closed",
            payload={},
            retry_count=4,  # max_retries=5, este es el intento 5
            max_retries=5,
        )

        result, status = process_webhook_delivery(
            delivery_id=delivery_id,
            event_type="issues",
            action="closed",
            payload={},
        )

        delivery.refresh_from_db()
        assert delivery.status == "dead_letter"
        assert delivery.retry_count == 5
        assert delivery.next_retry_at is None

    @patch("apps.integrations.webhook_processor._handle_issue_event")
    def test_dlq_no_se_reprocesa(self, mock_handler):
        """Un webhook en DLQ no se reprocesa automáticamente."""
        delivery = WebhookDelivery.objects.create(
            delivery_id="delivery-dead-001",
            event_type="issues",
            action="closed",
            payload={},
            status=WebhookDelivery.Status.DEAD_LETTER,
        )

        result, status = process_webhook_delivery(
            delivery_id="delivery-dead-001",
            event_type="issues",
            action="closed",
            payload={},
        )

        assert status == 200
        assert "DLQ" in result["message"]
        mock_handler.assert_not_called()

    @patch("apps.integrations.tasks.process_webhook_retry_task.delay")
    def test_reintentar_dlq_manualmente(self, mock_delay):
        """retry_dead_letter_deliveries reinicia y encola entregas en DLQ."""
        WebhookDelivery.objects.create(
            delivery_id="delivery-retry-001",
            event_type="issues",
            action="closed",
            payload={},
            status=WebhookDelivery.Status.DEAD_LETTER,
            retry_count=5,
        )
        WebhookDelivery.objects.create(
            delivery_id="delivery-retry-002",
            event_type="issues",
            action="opened",
            payload={},
            status=WebhookDelivery.Status.DEAD_LETTER,
            retry_count=5,
        )

        result = retry_dead_letter_deliveries()
        assert "2" in result
        assert mock_delay.call_count == 2

        # Verificar que se resetearon
        for d in WebhookDelivery.objects.filter(delivery_id__startswith="delivery-retry"):
            assert d.status == "pending"
            assert d.retry_count == 0


@pytest.mark.django_db
class TestWebhookDeliveryAPI:
    def test_listar_entregas(self, authed_client):
        WebhookDelivery.objects.create(
            delivery_id="del-1",
            event_type="issues",
            action="opened",
            payload={},
            status="processed",
        )
        resp = authed_client.get("/api/webhooks/deliveries/")
        assert resp.status_code == 200
        assert len(resp.data) == 1
        assert resp.data[0]["delivery_id"] == "del-1"

    def test_reintentar_dlq_endpoint(self, authed_client):
        WebhookDelivery.objects.create(
            delivery_id="del-dlq",
            event_type="issues",
            action="closed",
            payload={},
            status="dead_letter",
        )
        with patch("apps.integrations.tasks.process_webhook_retry_task.delay"):
            resp = authed_client.post("/api/webhooks/retry-dead-letter/")
        assert resp.status_code == 200
        assert "1" in resp.data["message"]


@pytest.mark.django_db
class TestWebhookPRAndRelease:
    @patch("apps.integrations.views.GitHubAppClient.verify_webhook_signature", return_value=True)
    def test_webhook_pull_request(self, mock_verify, api_client):
        payload = {
            "action": "opened",
            "pull_request": {"number": 42, "state": "open", "merged": False},
            "repository": {"full_name": "testuser/my-repo"},
        }
        resp = api_client.post(
            "/api/webhooks/github/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_GITHUB_EVENT="pull_request",
            HTTP_X_GITHUB_DELIVERY="delivery-pr-001",
        )
        assert resp.status_code == 200
        assert "PR #42" in resp.data["message"]

    @patch("apps.integrations.views.GitHubAppClient.verify_webhook_signature", return_value=True)
    def test_webhook_release(self, mock_verify, api_client):
        payload = {
            "action": "published",
            "release": {"tag_name": "v1.0.0"},
            "repository": {"full_name": "testuser/my-repo"},
        }
        resp = api_client.post(
            "/api/webhooks/github/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_GITHUB_EVENT="release",
            HTTP_X_GITHUB_DELIVERY="delivery-release-001",
        )
        assert resp.status_code == 200
        assert "v1.0.0" in resp.data["message"]
