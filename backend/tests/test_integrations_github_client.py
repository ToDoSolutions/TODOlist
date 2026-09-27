from unittest.mock import Mock, patch

import pytest
from django.test import override_settings

from apps.integrations.github_client import GitHubAppClient, GitHubOAuthClient


@pytest.mark.django_db
class TestGitHubAppClient:
    def test_generate_jwt(self):
        with override_settings(GITHUB_APP_ID="123", GITHUB_APP_PRIVATE_KEY="fake-key"):
            client = GitHubAppClient(installation_id=456)
            with patch("apps.integrations.github_client.jwt.encode") as mock_jwt:
                mock_jwt.return_value = "jwt-token"
                token = client._generate_jwt()
                assert token == "jwt-token"
                mock_jwt.assert_called_once()

    def test_generate_jwt_no_key(self):
        with override_settings(GITHUB_APP_ID="123", GITHUB_APP_PRIVATE_KEY=""):
            client = GitHubAppClient(installation_id=456)
            with pytest.raises(ValueError, match="GITHUB_APP_PRIVATE_KEY"):
                client._generate_jwt()

    def test_get_installation_token(self):
        with override_settings(GITHUB_APP_ID="123", GITHUB_APP_PRIVATE_KEY="fake-key"):
            client = GitHubAppClient(installation_id=456)
            with patch.object(client, "_generate_jwt", return_value="jwt"), \
                 patch("apps.integrations.github_client._request") as mock_req:
                mock_req.return_value = Mock(json=lambda: {"token": "inst-token"})
                token = client._get_installation_token()
                assert token == "inst-token"
                assert client._installation_token == "inst-token"

    def test_list_issues(self):
        with override_settings(GITHUB_APP_ID="123", GITHUB_APP_PRIVATE_KEY="fake-key"):
            client = GitHubAppClient(installation_id=456)
            client._installation_token = "token"
            with patch("apps.integrations.github_client._request") as mock_req:
                mock_req.return_value = Mock(json=lambda: [{"number": 1}])
                issues = client.list_issues("owner", "repo")
                assert issues == [{"number": 1}]
                mock_req.assert_called_once_with(
                    "GET",
                    "https://api.github.com/repos/owner/repo/issues",
                    headers={"Authorization": "token token", "Accept": "application/vnd.github+json"},
                    params={"state": "open", "per_page": 100},
                )

    def test_create_issue(self):
        with override_settings(GITHUB_APP_ID="123", GITHUB_APP_PRIVATE_KEY="fake-key"):
            client = GitHubAppClient(installation_id=456)
            client._installation_token = "token"
            with patch("apps.integrations.github_client._request") as mock_req:
                mock_req.return_value = Mock(json=lambda: {"number": 2})
                issue = client.create_issue("owner", "repo", "Title", "Body", ["bug"])
                assert issue["number"] == 2
                mock_req.assert_called_once_with(
                    "POST",
                    "https://api.github.com/repos/owner/repo/issues",
                    headers={"Authorization": "token token", "Accept": "application/vnd.github+json"},
                    json={"title": "Title", "body": "Body", "labels": ["bug"]},
                )

    def test_update_issue(self):
        with override_settings(GITHUB_APP_ID="123", GITHUB_APP_PRIVATE_KEY="fake-key"):
            client = GitHubAppClient(installation_id=456)
            client._installation_token = "token"
            with patch("apps.integrations.github_client._request") as mock_req:
                mock_req.return_value = Mock(json=lambda: {"number": 1})
                issue = client.update_issue("owner", "repo", 1, state="closed")
                assert issue["number"] == 1
                mock_req.assert_called_once_with(
                    "PATCH",
                    "https://api.github.com/repos/owner/repo/issues/1",
                    headers={"Authorization": "token token", "Accept": "application/vnd.github+json"},
                    json={"state": "closed"},
                )

    def test_list_pull_requests(self):
        with override_settings(GITHUB_APP_ID="123", GITHUB_APP_PRIVATE_KEY="fake-key"):
            client = GitHubAppClient(installation_id=456)
            client._installation_token = "token"
            with patch("apps.integrations.github_client._request") as mock_req:
                mock_req.return_value = Mock(json=lambda: [{"number": 5}])
                prs = client.list_pull_requests("owner", "repo")
                assert prs == [{"number": 5}]

    def test_verify_webhook_signature(self):
        with override_settings(GITHUB_APP_WEBHOOK_SECRET="secret"):
            import hashlib
            import hmac
            payload = b"test payload"
            signature = "sha256=" + hmac.new(b"secret", payload, hashlib.sha256).hexdigest()
            assert GitHubAppClient.verify_webhook_signature(payload, signature) is True
            assert GitHubAppClient.verify_webhook_signature(payload, "invalid") is False
            assert GitHubAppClient.verify_webhook_signature(payload, "") is False

    def test_verify_webhook_signature_no_secret(self):
        """Sin secret configurado, toda firma se rechaza."""
        with override_settings(GITHUB_APP_WEBHOOK_SECRET=""):
            assert GitHubAppClient.verify_webhook_signature(b"x", "sha256=abc") is False


@pytest.mark.django_db
class TestGitHubOAuthClient:
    def test_get_authorize_url(self):
        with override_settings(GITHUB_APP_CLIENT_ID="cid"):
            client = GitHubOAuthClient()
            url = client.get_authorize_url("http://localhost/callback", "state123")
            assert "client_id=cid" in url
            assert "redirect_uri=http%3A%2F%2Flocalhost%2Fcallback" in url
            assert "state=state123" in url

    def test_exchange_code(self):
        with override_settings(GITHUB_APP_CLIENT_ID="cid", GITHUB_APP_CLIENT_SECRET="secret"):
            client = GitHubOAuthClient()
            with patch("apps.integrations.github_client._request") as mock_req:
                mock_req.return_value = Mock(json=lambda: {"access_token": "tok"})
                result = client.exchange_code("code123", "http://localhost/callback")
                assert result["access_token"] == "tok"

    def test_get_user_info(self):
        client = GitHubOAuthClient()
        with patch("apps.integrations.github_client._request") as mock_req:
            mock_req.return_value = Mock(json=lambda: {"login": "user"})
            result = client.get_user_info("tok")
            assert result["login"] == "user"

    def test_get_verified_emails(self):
        """Solo emails verificados se devuelven."""
        client = GitHubOAuthClient()
        with patch("apps.integrations.github_client._request") as mock_req:
            mock_req.return_value = Mock(json=lambda: [
                {"email": "a@a.com", "verified": True},
                {"email": "b@b.com", "verified": False},
            ])
            result = client.get_verified_emails("tok")
            assert result == {"a@a.com"}

    def test_get_verified_emails_error(self):
        """Si la API falla, retorna set vacío (no crashea)."""
        client = GitHubOAuthClient()
        with patch("apps.integrations.github_client._request", side_effect=Exception("boom")):
            assert client.get_verified_emails("tok") == set()
