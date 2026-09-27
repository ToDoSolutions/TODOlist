"""Tests dirigidos a github_client: traducción de errores, params y payload."""
from unittest.mock import Mock, patch

import pytest
import requests
from django.test import override_settings

from apps.integrations.exceptions import (
    AuthenticationExpired,
    ExternalRateLimited,
    ExternalResourceNotFound,
    ExternalServiceUnavailable,
)
from apps.integrations.github_client import (
    DEFAULT_HTTP_TIMEOUT,
    GitHubAppClient,
    GitHubOAuthClient,
    _request,
)


def _resp(status=200, text="", json_data=None):
    r = Mock()
    r.status_code = status
    r.text = text
    r.json.return_value = json_data or {}
    r.raise_for_status = Mock()
    return r


class TestRequest:
    def test_ok_devuelve_resp(self):
        with patch("apps.integrations.github_client.requests.request",
                   return_value=_resp(200)) as m:
            resp = _request("GET", "http://x")
        assert resp.status_code == 200
        assert m.call_args.kwargs["timeout"] == DEFAULT_HTTP_TIMEOUT

    def test_timeout_respetado_si_dado(self):
        with patch("apps.integrations.github_client.requests.request",
                   return_value=_resp(200)) as m:
            _request("GET", "http://x", timeout=3)
        assert m.call_args.kwargs["timeout"] == 3

    def test_request_exception_a_unavailable(self):
        with patch("apps.integrations.github_client.requests.request",
                   side_effect=requests.ConnectionError("down")), \
                pytest.raises(ExternalServiceUnavailable):
                _request("GET", "http://x")

    def test_401_bad_credentials(self):
        with patch("apps.integrations.github_client.requests.request",
                   return_value=_resp(401, "Bad credentials")), \
                pytest.raises(AuthenticationExpired):
                _request("GET", "http://x")

    def test_403_bad_credentials(self):
        with patch("apps.integrations.github_client.requests.request",
                   return_value=_resp(403, "Bad credentials")), \
                pytest.raises(AuthenticationExpired):
                _request("GET", "http://x")

    def test_403_rate_limit(self):
        with patch("apps.integrations.github_client.requests.request",
                   return_value=_resp(403, "API rate limit exceeded")), \
                pytest.raises(ExternalRateLimited):
                _request("GET", "http://x")

    def test_429_rate_limit(self):
        with patch("apps.integrations.github_client.requests.request",
                   return_value=_resp(429)), pytest.raises(ExternalRateLimited):
            _request("GET", "http://x")

    def test_404_not_found(self):
        with patch("apps.integrations.github_client.requests.request",
                   return_value=_resp(404)), pytest.raises(ExternalResourceNotFound):
            _request("GET", "http://x")

    def test_500_unavailable(self):
        with patch("apps.integrations.github_client.requests.request",
                   return_value=_resp(502)), pytest.raises(ExternalServiceUnavailable):
            _request("GET", "http://x")

    def test_403_otro_error_no_mapea(self):
        """403 sin 'Bad credentials' ni 'rate limit' no lanza excepción."""
        with patch("apps.integrations.github_client.requests.request",
                   return_value=_resp(403, "Forbidden other")):
            resp = _request("GET", "http://x")
        assert resp.status_code == 403

    def test_400_no_mapea(self):
        with patch("apps.integrations.github_client.requests.request",
                   return_value=_resp(400)):
            resp = _request("GET", "http://x")
        assert resp.status_code == 400


class TestGitHubAppClient:
    def _client(self):
        with override_settings(
            GITHUB_APP_ID="123", GITHUB_APP_PRIVATE_KEY=""
        ):
            return GitHubAppClient(installation_id=99)

    def test_jwt_sin_key_error(self):
        with pytest.raises(ValueError, match="PRIVATE_KEY"):
            self._client()._generate_jwt()

    def test_jwt_payload(self):
        key = """-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA7Vbj7W+sZNEfzhBDNEn9d0DGNvBuvH4n5h0z2XJ0Wzv9z0RH
-----END RSA PRIVATE KEY-----"""
        with override_settings(GITHUB_APP_PRIVATE_KEY=key), \
             patch("apps.integrations.github_client.jwt.encode",
                   return_value="tok") as enc, override_settings(GITHUB_APP_ID="123",
                               GITHUB_APP_PRIVATE_KEY=key):
            GitHubAppClient(99)._generate_jwt()
        payload = enc.call_args.args[0]
        assert payload["iss"] == "123"
        assert payload["exp"] > payload["iat"]
        assert enc.call_args.kwargs["algorithm"] == "RS256"

    def test_installation_token_cacheado(self):
        c = self._client()
        c._installation_token = "cached"
        assert c._get_installation_token() == "cached"

    def test_installation_token_fetch(self):
        resp = _resp(201, json_data={"token": "new_tok"})
        with patch.object(
            GitHubAppClient, "_generate_jwt", return_value="j"
        ), patch(
            "apps.integrations.github_client._request", return_value=resp
        ) as req:
            tok = self._client()._get_installation_token()
        assert tok == "new_tok"
        assert "installations/99/access_tokens" in req.call_args.args[1]

    def test_headers_usa_token(self):
        c = self._client()
        c._installation_token = "tok"
        h = c._headers()
        assert h["Authorization"] == "token tok"
        assert "vnd.github" in h["Accept"]

    def _call_with_mock(self, method, *args, **kw):
        resp = _resp(200, json_data={"items": [1]})
        c = self._client()
        c._installation_token = "t"
        with patch(
            "apps.integrations.github_client._request", return_value=resp
        ) as req:
            getattr(c, method)(*args, **kw)
        return req, resp

    def test_list_issues_params(self):
        req, _ = self._call_with_mock("list_issues", "o", "r")
        _, url = req.call_args.args
        assert url == "https://api.github.com/repos/o/r/issues"
        assert req.call_args.kwargs["params"]["state"] == "open"
        assert req.call_args.kwargs["params"]["per_page"] == 100

    def test_get_issue_url(self):
        req, _ = self._call_with_mock("get_issue", "o", "r", 42)
        assert "/issues/42" in req.call_args.args[1]

    def test_create_issue_sin_labels(self):
        req, _ = self._call_with_mock("create_issue", "o", "r", "T")
        body = req.call_args.kwargs["json"]
        assert body == {"title": "T", "body": ""}
        assert "labels" not in body

    def test_create_issue_con_labels(self):
        req, _ = self._call_with_mock(
            "create_issue", "o", "r", "T", labels=["bug"]
        )
        assert req.call_args.kwargs["json"]["labels"] == ["bug"]

    def test_update_issue_solo_state(self):
        req, _ = self._call_with_mock(
            "update_issue", "o", "r", 5, state="closed"
        )
        body = req.call_args.kwargs["json"]
        assert body == {"state": "closed"}

    def test_update_issue_todos_campos(self):
        req, _ = self._call_with_mock(
            "update_issue", "o", "r", 5,
            state="open", title="T", body="B",
        )
        body = req.call_args.kwargs["json"]
        assert body == {"state": "open", "title": "T", "body": "B"}

    def test_list_prs_params(self):
        req, _ = self._call_with_mock(
            "list_pull_requests", "o", "r", state="closed", per_page=10,
            sort="created", direction="asc",
        )
        p = req.call_args.kwargs["params"]
        assert p == {"state": "closed", "per_page": 10,
                     "sort": "created", "direction": "asc"}

    def test_list_commits_url(self):
        req, _ = self._call_with_mock("list_commits", "o", "r", per_page=5)
        assert "/commits" in req.call_args.args[1]
        assert req.call_args.kwargs["params"]["per_page"] == 5

    def test_list_releases_url(self):
        req, _ = self._call_with_mock("list_releases", "o", "r")
        assert "/releases" in req.call_args.args[1]

    def test_check_runs_sin_ref_usa_head(self):
        resp = _resp(200, json_data={"check_runs": [1, 2]})
        c = self._client()
        c._installation_token = "t"
        with patch("apps.integrations.github_client._request",
                   return_value=resp) as req:
            runs = c.list_check_runs("o", "r")
        assert "/commits/HEAD/check-runs" in req.call_args.args[1]
        assert runs == [1, 2]

    def test_check_runs_con_ref(self):
        resp = _resp(200, json_data={"check_runs": []})
        c = self._client()
        c._installation_token = "t"
        with patch("apps.integrations.github_client._request",
                   return_value=resp) as req:
            c.list_check_runs("o", "r", ref="main")
        assert "/commits/main/check-runs" in req.call_args.args[1]

    def test_installation_repos_devuelve_lista(self):
        resp = _resp(200, json_data={"repositories": [{"id": 1}]})
        c = self._client()
        c._installation_token = "t"
        with patch("apps.integrations.github_client._request",
                   return_value=resp):
            repos = c.list_installation_repos()
        assert repos == [{"id": 1}]

    def test_graphql_payload(self):
        resp = _resp(200, json_data={"data": {}})
        c = self._client()
        c._installation_token = "t"
        with patch("apps.integrations.github_client._request",
                   return_value=resp) as req:
            c.graphql("query{viewer}", {"v": 1})
        assert req.call_args.args[1] == GitHubAppClient.GRAPHQL_URL
        assert req.call_args.kwargs["json"]["variables"] == {"v": 1}

    def test_graphql_variables_default(self):
        resp = _resp(200, json_data={"data": {}})
        c = self._client()
        c._installation_token = "t"
        with patch("apps.integrations.github_client._request",
                   return_value=resp) as req:
            c.graphql("query{viewer}")
        assert req.call_args.kwargs["json"]["variables"] == {}


class TestWebhookSignature:
    @pytest.fixture(autouse=True)
    def _secret(self):
        with override_settings(GITHUB_APP_WEBHOOK_SECRET="s3cret"):
            yield

    def _sig(self, body):
        import hashlib
        import hmac
        return "sha256=" + hmac.new(
            b"s3cret", body, hashlib.sha256
        ).hexdigest()

    def test_firma_valida(self):
        body = b'{"a":1}'
        assert GitHubAppClient.verify_webhook_signature(
            body, self._sig(body)
        ) is True

    def test_firma_invalida(self):
        assert GitHubAppClient.verify_webhook_signature(
            b"body", "sha256=bad"
        ) is False

    def test_sin_header_false(self):
        assert GitHubAppClient.verify_webhook_signature(b"b", "") is False
        assert GitHubAppClient.verify_webhook_signature(b"b", None) is False

    def test_sin_secret_rechaza(self):
        body = b"x"
        with override_settings(GITHUB_APP_WEBHOOK_SECRET=""):
            assert GitHubAppClient.verify_webhook_signature(
                body, self._sig(body)
            ) is False

    def test_body_modificado_firma_falla(self):
        assert GitHubAppClient.verify_webhook_signature(
            b"otro body", self._sig(b"body")
        ) is False


class TestOAuthClient:
    @pytest.fixture(autouse=True)
    def _creds(self):
        with override_settings(
            GITHUB_APP_CLIENT_ID="cid", GITHUB_APP_CLIENT_SECRET="csec"
        ):
            yield

    def test_authorize_url_params(self):
        c = GitHubOAuthClient()
        url = c.get_authorize_url("https://cb", state="s1")
        assert url.startswith(GitHubOAuthClient.AUTHORIZE_URL)
        assert "client_id=cid" in url
        assert "state=s1" in url
        assert "redirect_uri=https%3A%2F%2Fcb" in url

    def test_exchange_code_payload(self):
        resp = _resp(200, json_data={"access_token": "tok"})
        with patch("apps.integrations.github_client._request",
                   return_value=resp) as req:
            data = GitHubOAuthClient().exchange_code("code123", "https://cb")
        assert data["access_token"] == "tok"
        body = req.call_args.kwargs["json"]
        assert body["code"] == "code123"
        assert body["client_secret"] == "csec"

    def test_get_user_info_headers(self):
        resp = _resp(200, json_data={"login": "u"})
        with patch("apps.integrations.github_client._request",
                   return_value=resp) as req:
            info = GitHubOAuthClient().get_user_info("tok")
        assert info["login"] == "u"
        assert req.call_args.kwargs["headers"]["Authorization"] == "token tok"

    def test_verified_emails_solo_verificados(self):
        resp = _resp(200, json_data=[
            {"email": "a@x.com", "verified": True},
            {"email": "b@x.com", "verified": False},
            {"email": None, "verified": True},
            {"email": "C@X.COM", "verified": True},
        ])
        with patch("apps.integrations.github_client._request",
                   return_value=resp):
            emails = GitHubOAuthClient().get_verified_emails("tok")
        assert emails == {"a@x.com", "c@x.com"}

    def test_verified_emails_error_devuelve_vacio(self):
        with patch("apps.integrations.github_client._request",
                   side_effect=Exception("net")):
            assert GitHubOAuthClient().get_verified_emails("tok") == set()
