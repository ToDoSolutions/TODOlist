"""Tests exhaustivos para integrations/views.py (parte 2)."""
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import RequestFactory

from apps.integrations.views import github_oauth_start, oauth_providers

User = get_user_model()


@pytest.mark.django_db
class TestOAuthProviders:
    def test_oauth_providers(self):
        """Verifica que retorna providers configurados."""
        factory = RequestFactory()
        request = factory.get("/api/oauth/providers/")
        response = oauth_providers(request)
        assert response.status_code == 200
        assert "github" in response.data
        assert "google" in response.data

    def test_github_oauth_start(self):
        """Verifica que genera URL de autorización."""
        factory = RequestFactory()
        request = factory.get("/api/github/oauth/start/")
        # Simular sesión
        request.session = {}
        response = github_oauth_start(request)
        assert response.status_code == 200
        assert "auth_url" in response.data
        assert "state" in response.data
        assert "github_oauth_state" in request.session


@pytest.mark.django_db
class TestGitHubOAuthCallback:
    def test_invalid_state(self):
        """Verifica que rechaza state inválido."""
        from apps.integrations.views import github_oauth_callback
        factory = RequestFactory()
        request = factory.post("/api/github/oauth/callback/", {
            "code": "abc", "state": "invalid"
        })
        request.session = {"github_oauth_state": "different"}
        response = github_oauth_callback(request)
        assert response.status_code == 400
        assert "inválidos" in response.data["error"]

    def test_missing_code(self):
        """Verifica que rechaza si falta code."""
        from apps.integrations.views import github_oauth_callback
        factory = RequestFactory()
        request = factory.post("/api/github/oauth/callback/", {
            "state": "abc"
        })
        request.session = {"github_oauth_state": "abc"}
        response = github_oauth_callback(request)
        assert response.status_code == 400


@pytest.mark.django_db
class TestGitHubWebhook:
    def test_invalid_signature(self):
        """Verifica que rechaza firma inválida."""
        from apps.integrations.views import github_webhook
        factory = RequestFactory()
        request = factory.post(
            "/api/webhooks/github/",
            data=b'{"action": "opened"}',
            content_type="application/json"
        )
        request.headers = {"X-Hub-Signature-256": "invalid"}
        with patch("apps.integrations.views.GitHubAppClient.verify_webhook_signature", return_value=False):
            response = github_webhook(request)
            assert response.status_code == 401
            assert "Firma inválida" in response.data["error"]

    def test_valid_signature(self):
        """Verifica que procesa webhook con firma válida."""
        from apps.integrations.views import github_webhook
        factory = RequestFactory()
        request = factory.post(
            "/api/webhooks/github/",
            data=b'{"action": "opened", "repository": {"full_name": "org/repo"}}',
            content_type="application/json"
        )
        request.headers = {
            "X-Hub-Signature-256": "valid",
            "X-GitHub-Event": "issues",
            "X-GitHub-Delivery": "delivery-123",
        }
        with (
            patch("apps.integrations.views.GitHubAppClient.verify_webhook_signature", return_value=True),
            patch("apps.integrations.webhook_processor.process_webhook_delivery") as mock_process,
        ):
            mock_process.return_value = ({"message": "ok"}, 200)
            response = github_webhook(request)
            assert response.status_code == 200
