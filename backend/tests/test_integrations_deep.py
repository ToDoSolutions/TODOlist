"""Tests de borde para sync_github, github_client (_request) y webhook_processor."""
from unittest.mock import Mock, patch

import pytest
from django.contrib.auth import get_user_model

from apps.integrations.models import (
    GitHubCheckRun,
    GitHubCommit,
    GitHubInstallation,
    GitHubIssueLink,
    GitHubPullRequest,
    GitHubRelease,
    GitHubRepo,
)
from apps.integrations.sync_github import (
    sync_check_runs,
    sync_commits,
    sync_pull_requests,
    sync_releases,
    sync_repo_data,
)
from apps.tasks.models import Task

User = get_user_model()


@pytest.fixture
def user(db):
    u, _ = User.objects.get_or_create(
        username="int_u", defaults={"email": "int@x.com"}
    )
    return u


@pytest.fixture
def installation(user):
    return GitHubInstallation.objects.create(
        user=user, installation_id=1001, account_login="u",
    )


@pytest.fixture
def repo(installation):
    return GitHubRepo.objects.create(
        installation=installation, repo_id=100, name="r", owner="o",
        full_name="o/r", sync_enabled=True,
    )


def _client(**methods):
    c = Mock()
    for k, v in methods.items():
        setattr(c, k, Mock(return_value=v))
    return c


@pytest.mark.django_db
class TestSyncPullRequests:
    def test_campos_guardados(self, repo, installation):
        client = _client(list_pull_requests=[
            {
                "id": 10, "number": 5, "title": "Fix bug", "state": "open",
                "merged": False, "draft": True,
                "html_url": "http://x", "head": {"ref": "feat"},
                "base": {"ref": "main"}, "user": {"login": "dev"},
                "created_at": "2024-01-01T00:00:00Z",
                "merged_at": None, "closed_at": None,
                "review_comments": 7,
            }
        ])
        with patch("apps.integrations.sync_github._get_client", return_value=client):
            n = sync_pull_requests(repo, installation)
        assert n == 1
        pr = GitHubPullRequest.objects.get()
        assert pr.title == "Fix bug"
        assert pr.is_draft is True
        assert pr.head_branch == "feat"
        assert pr.base_branch == "main"
        assert pr.author == "dev"
        assert pr.review_comments_count == 7

    def test_dedup_por_pr_id(self, repo, installation):
        pr = {"id": 10, "number": 5, "title": "t"}
        client = _client(list_pull_requests=[pr, pr])
        with patch("apps.integrations.sync_github._get_client", return_value=client):
            n = sync_pull_requests(repo, installation)
        assert n == 1  # mismo pr_id en open y closed no se duplica

    def test_pr_sin_id_se_omite(self, repo, installation):
        client = _client(list_pull_requests=[{"number": 5, "title": "sin id"}])
        with patch("apps.integrations.sync_github._get_client", return_value=client):
            n = sync_pull_requests(repo, installation)
        assert n == 0
        assert GitHubPullRequest.objects.count() == 0

    def test_error_un_estado_continua_otro(self, repo, installation):
        import requests as req
        client = _client()
        def list_prs(*a, **kw):
            if kw.get("state") == "open":
                raise req.RequestException("API caída")
            return [{"id": 9, "number": 3, "title": "closed pr"}]
        client.list_pull_requests = Mock(side_effect=list_prs)
        with patch("apps.integrations.sync_github._get_client", return_value=client):
            n = sync_pull_requests(repo, installation)
        assert n == 1

    def test_vincula_issues_referenciados(self, repo, installation, user):
        task = Task.objects.create(owner=user, title="t")
        GitHubIssueLink.objects.create(
            task=task, repo=repo, issue_number=42, issue_id=1,
        )
        client = _client(list_pull_requests=[
            {"id": 10, "number": 5, "title": "Fix", "body": "closes #42"},
        ])
        with patch("apps.integrations.sync_github._get_client", return_value=client):
            sync_pull_requests(repo, installation)
        pr = GitHubPullRequest.objects.get()
        assert pr.tasks.filter(id=task.id).exists()

    def test_pr_sin_referencias_no_vincula(self, repo, installation, user):
        task = Task.objects.create(owner=user, title="t")
        GitHubIssueLink.objects.create(
            task=task, repo=repo, issue_number=42, issue_id=1,
        )
        client = _client(list_pull_requests=[
            {"id": 10, "number": 5, "title": "Sin refs"},
        ])
        with patch("apps.integrations.sync_github._get_client", return_value=client):
            sync_pull_requests(repo, installation)
        pr = GitHubPullRequest.objects.get()
        assert not pr.tasks.exists()

    def test_update_or_create_actualiza(self, repo, installation):
        GitHubPullRequest.objects.create(
            repo=repo, pr_number=5, pr_id=10, title="viejo", state="open",
        )
        client = _client(list_pull_requests=[
            {"id": 10, "number": 5, "title": "nuevo", "state": "closed"},
        ])
        with patch("apps.integrations.sync_github._get_client", return_value=client):
            sync_pull_requests(repo, installation)
        assert GitHubPullRequest.objects.count() == 1
        assert GitHubPullRequest.objects.get().title == "nuevo"


@pytest.mark.django_db
class TestSyncCommits:
    def test_campos(self, repo, installation):
        client = _client(list_commits=[
            {
                "sha": "abc123", "html_url": "http://c",
                "commit": {
                    "message": "msg",
                    "author": {"name": "dev", "date": "2024-01-01T00:00:00Z"},
                },
                "author": {"login": "ghuser"},
            }
        ])
        with patch("apps.integrations.sync_github._get_client", return_value=client):
            n = sync_commits(repo, installation)
        assert n == 1
        c = GitHubCommit.objects.get()
        assert c.sha == "abc123"
        assert c.message == "msg"
        assert c.author == "dev"  # prefiere commit.author.name

    def test_author_fallback_a_login(self, repo, installation):
        client = _client(list_commits=[
            {
                "sha": "abc", "commit": {"message": "m", "author": {}},
                "author": {"login": "ghuser"},
            }
        ])
        with patch("apps.integrations.sync_github._get_client", return_value=client):
            sync_commits(repo, installation)
        assert GitHubCommit.objects.get().author == "ghuser"

    def test_sin_sha_se_omite(self, repo, installation):
        client = _client(list_commits=[{"commit": {"message": "m"}}])
        with patch("apps.integrations.sync_github._get_client", return_value=client):
            n = sync_commits(repo, installation)
        assert n == 0

    def test_error_api_retorna_0(self, repo, installation):
        import requests as req
        client = _client()
        client.list_commits = Mock(
            side_effect=req.RequestException("timeout")
        )
        with patch("apps.integrations.sync_github._get_client", return_value=client):
            n = sync_commits(repo, installation)
        assert n == 0


@pytest.mark.django_db
class TestSyncReleases:
    def test_campos(self, repo, installation):
        client = _client(list_releases=[
            {
                "id": 7, "tag_name": "v1.0", "name": "Release",
                "body": "notes", "html_url": "http://r",
                "prerelease": True, "author": {"login": "dev"},
                "published_at": "2024-01-01T00:00:00Z",
            }
        ])
        with patch("apps.integrations.sync_github._get_client", return_value=client):
            n = sync_releases(repo, installation)
        assert n == 1
        r = GitHubRelease.objects.get()
        assert r.tag_name == "v1.0"
        assert r.state == "prerelease"
        assert r.is_prerelease is True

    def test_release_publicada(self, repo, installation):
        client = _client(list_releases=[
            {"id": 7, "tag_name": "v1", "prerelease": False},
        ])
        with patch("apps.integrations.sync_github._get_client", return_value=client):
            sync_releases(repo, installation)
        assert GitHubRelease.objects.get().state == "published"

    def test_sin_id_se_omite(self, repo, installation):
        client = _client(list_releases=[{"tag_name": "v1"}])
        with patch("apps.integrations.sync_github._get_client", return_value=client):
            n = sync_releases(repo, installation)
        assert n == 0


@pytest.mark.django_db
class TestSyncCheckRuns:
    def test_campos(self, repo, installation):
        client = _client(list_check_runs=[
            {
                "id": 3, "name": "CI", "status": "completed",
                "conclusion": "success", "html_url": "http://ch",
                "started_at": "2024-01-01T00:00:00Z",
                "completed_at": "2024-01-01T00:05:00Z",
                "head_sha": "abc",
            }
        ])
        with patch("apps.integrations.sync_github._get_client", return_value=client):
            n = sync_check_runs(repo, installation)
        assert n == 1
        ch = GitHubCheckRun.objects.get()
        assert ch.name == "CI"
        assert ch.conclusion == "success"
        assert ch.commit_sha == "abc"

    def test_asocia_a_pr_y_actualiza_ci(self, repo, installation):
        pr = GitHubPullRequest.objects.create(
            repo=repo, pr_number=9, pr_id=1, title="p",
        )
        client = _client(list_check_runs=[
            {
                "id": 3, "name": "CI", "status": "completed",
                "conclusion": "failure", "html_url": "http://ch",
                "pull_requests": [{"number": 9}],
            }
        ])
        with patch("apps.integrations.sync_github._get_client", return_value=client):
            sync_check_runs(repo, installation)
        ch = GitHubCheckRun.objects.get()
        pr.refresh_from_db()
        assert ch.pull_request == pr
        assert pr.ci_status == "failure"
        assert pr.ci_url == "http://ch"

    def test_check_sin_pr(self, repo, installation):
        client = _client(list_check_runs=[
            {"id": 3, "name": "CI", "status": "completed"},
        ])
        with patch("apps.integrations.sync_github._get_client", return_value=client):
            sync_check_runs(repo, installation)
        assert GitHubCheckRun.objects.get().pull_request is None


@pytest.mark.django_db
class TestSyncRepoData:
    def test_sync_disabled_no_hace_nada(self, repo):
        repo.sync_enabled = False
        repo.save()
        result = sync_repo_data(repo)
        assert result == {
            "pull_requests": 0, "commits": 0, "releases": 0, "check_runs": 0,
        }

    def test_resultado_conteos(self, repo, installation):
        client = _client(
            list_pull_requests=[{"id": 1, "number": 1}],
            list_commits=[{"sha": "a"}],
            list_releases=[{"id": 2}],
            list_check_runs=[{"id": 3}],
        )
        with patch("apps.integrations.sync_github._get_client", return_value=client):
            result = sync_repo_data(repo)
        assert result == {
            "pull_requests": 1, "commits": 1, "releases": 1, "check_runs": 1,
        }

    def test_error_en_una_seccion_no_detiene(self, repo, installation):
        import requests as req
        client = _client(
            list_commits=[{"sha": "a"}],
            list_releases=[{"id": 2}],
            list_check_runs=[{"id": 3}],
        )
        client.list_pull_requests = Mock(
            side_effect=req.RequestException("down")
        )
        with patch("apps.integrations.sync_github._get_client", return_value=client):
            result = sync_repo_data(repo)
        assert result["pull_requests"] == 0
        assert result["commits"] == 1


@pytest.mark.django_db
class TestRequestErrorTranslation:
    """_request traduce errores HTTP a excepciones de dominio."""

    def _resp(self, status, text=""):
        r = Mock()
        r.status_code = status
        r.text = text
        return r

    def test_401_bad_credentials(self):
        from apps.integrations.exceptions import AuthenticationExpired
        from apps.integrations.github_client import _request
        with patch("apps.integrations.github_client.requests.request",
                   return_value=self._resp(401, "Bad credentials")), pytest.raises(AuthenticationExpired):
            _request("GET", "http://x")

    def test_403_rate_limit(self):
        from apps.integrations.exceptions import ExternalRateLimited
        from apps.integrations.github_client import _request
        with patch("apps.integrations.github_client.requests.request",
                   return_value=self._resp(403, "rate limit exceeded")), pytest.raises(ExternalRateLimited):
            _request("GET", "http://x")

    def test_429(self):
        from apps.integrations.exceptions import ExternalRateLimited
        from apps.integrations.github_client import _request
        with patch("apps.integrations.github_client.requests.request",
                   return_value=self._resp(429)), pytest.raises(ExternalRateLimited):
            _request("GET", "http://x")

    def test_404(self):
        from apps.integrations.exceptions import ExternalResourceNotFound
        from apps.integrations.github_client import _request
        with patch("apps.integrations.github_client.requests.request",
                   return_value=self._resp(404)), pytest.raises(ExternalResourceNotFound):
            _request("GET", "http://x")

    def test_500(self):
        from apps.integrations.exceptions import ExternalServiceUnavailable
        from apps.integrations.github_client import _request
        with patch("apps.integrations.github_client.requests.request",
                   return_value=self._resp(502)), pytest.raises(ExternalServiceUnavailable):
            _request("GET", "http://x")

    def test_timeout_por_defecto(self):
        from apps.integrations.github_client import _request
        mock_req = Mock(return_value=self._resp(200))
        with patch("apps.integrations.github_client.requests.request", mock_req):
            _request("GET", "http://x")
        assert mock_req.call_args.kwargs["timeout"] == 15

    def test_ok_retorna_respuesta(self):
        from apps.integrations.github_client import _request
        resp = self._resp(200)
        with patch("apps.integrations.github_client.requests.request",
                   return_value=resp):
            assert _request("GET", "http://x") is resp


class TestWebhookDispatch:
    """_dispatch_event enruta eventos a sus handlers."""

    @pytest.mark.django_db
    def test_evento_desconocido_no_explota(self):
        from apps.integrations.webhook_processor import _dispatch_event
        _dispatch_event("unknown_event", "created", {})  # no raise

    @pytest.mark.django_db
    def test_dispatch_pr_event(self):
        from apps.integrations.webhook_processor import _dispatch_event
        with patch(
            "apps.integrations.webhook_processor._handle_pr_event"
        ) as h:
            _dispatch_event("pull_request", "opened", {"pull_request": {}})
            h.assert_called_once()
