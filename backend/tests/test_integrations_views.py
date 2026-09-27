import hashlib
import hmac
import json
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.integrations.models import (
    GitHubInstallation,
    GitHubIssueLink,
    GitHubPullRequest,
    GitHubRelease,
    GitHubRepo,
    WebhookDelivery,
)
from apps.tasks.models import Task

User = get_user_model()


@pytest.fixture
def api_client(db):
    return APIClient()


@pytest.fixture
def auth_client(api_client, db):
    user = User.objects.create_user(username="iv", email="iv@iv.com", password="pass")
    refresh = RefreshToken.for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return api_client, user


@pytest.mark.django_db
class TestGitHubInstallationViewSet:
    def test_list_installations(self, auth_client):
        client, user = auth_client
        GitHubInstallation.objects.create(user=user, installation_id=1)
        GitHubInstallation.objects.create(user=User.objects.create_user(username="o", email="o@o.com", password="p"), installation_id=2)
        resp = client.get("/api/github/installations/")
        assert resp.status_code == 200
        assert len(resp.data) == 1

    def test_repos(self, auth_client):
        client, user = auth_client
        inst = GitHubInstallation.objects.create(user=user, installation_id=1)
        GitHubRepo.objects.create(installation=inst, repo_id=1, full_name="a/b", name="b", owner="a")
        resp = client.get("/api/github/installations/repos/")
        assert resp.status_code == 200
        assert len(resp.data) == 1

    def test_discover_repos(self, auth_client):
        client, user = auth_client
        GitHubInstallation.objects.create(user=user, installation_id=1)
        with patch("apps.integrations.views.GitHubAppClient") as mock_client:
            mock_client.return_value.list_installation_repos.return_value = [
                {"id": 1, "full_name": "a/b", "name": "b", "owner": {"login": "a"}, "private": False, "default_branch": "main"},
            ]
            resp = client.post("/api/github/installations/discover_repos/")
            assert resp.status_code == 200
            assert resp.data["total"] == 1
            assert resp.data["new"] == 1
            assert GitHubRepo.objects.filter(full_name="a/b").exists()

    def test_discover_repos_no_installation(self, auth_client):
        client, _ = auth_client
        resp = client.post("/api/github/installations/discover_repos/")
        assert resp.status_code == 400

    def test_discover_repos_error(self, auth_client):
        client, user = auth_client
        GitHubInstallation.objects.create(user=user, installation_id=1)
        with patch("apps.integrations.views.GitHubAppClient") as mock_client:
            mock_client.return_value.list_installation_repos.side_effect = Exception("API error")
            resp = client.post("/api/github/installations/discover_repos/")
            assert resp.status_code == 502


@pytest.mark.django_db
class TestGitHubRepoViewSet:
    def test_list_repos(self, auth_client):
        client, user = auth_client
        inst = GitHubInstallation.objects.create(user=user, installation_id=1)
        GitHubRepo.objects.create(installation=inst, repo_id=1, full_name="a/b", name="b", owner="a")
        resp = client.get("/api/github/repos/")
        assert resp.status_code == 200
        assert len(resp.data) == 1

    def test_sync_repo(self, auth_client):
        client, user = auth_client
        inst = GitHubInstallation.objects.create(user=user, installation_id=1)
        repo = GitHubRepo.objects.create(installation=inst, repo_id=1, full_name="a/b", name="b", owner="a", sync_enabled=True)
        with patch("apps.integrations.views.sync_repo_issues_task"), \
             patch("apps.integrations.sync_github.sync_repo_data", return_value={"pull_requests": 1, "commits": 2, "releases": 0, "check_runs": 3}):
            resp = client.post(f"/api/github/repos/{repo.id}/sync/")
            assert resp.status_code == 200
            assert resp.data["synced"]["pull_requests"] == 1

    def test_sync_repo_disabled(self, auth_client):
        client, user = auth_client
        inst = GitHubInstallation.objects.create(user=user, installation_id=1)
        repo = GitHubRepo.objects.create(installation=inst, repo_id=1, full_name="a/b", name="b", owner="a", sync_enabled=False)
        resp = client.post(f"/api/github/repos/{repo.id}/sync/")
        assert resp.status_code == 400

    def test_issues(self, auth_client):
        client, user = auth_client
        inst = GitHubInstallation.objects.create(user=user, installation_id=1)
        repo = GitHubRepo.objects.create(installation=inst, repo_id=1, full_name="a/b", name="b", owner="a")
        with patch("apps.integrations.views.GitHubAppClient") as mock_client:
            mock_client.return_value.list_issues.return_value = [
                {"id": 1, "number": 1, "title": "Issue", "state": "open", "html_url": "http://x", "body": "", "labels": []},
            ]
            resp = client.get(f"/api/github/repos/{repo.id}/issues/")
            assert resp.status_code == 200
            assert len(resp.data["results"]) == 1
            assert resp.data["results"][0]["already_linked"] is False

    def test_import_issues(self, auth_client):
        client, user = auth_client
        inst = GitHubInstallation.objects.create(user=user, installation_id=1)
        repo = GitHubRepo.objects.create(installation=inst, repo_id=1, full_name="a/b", name="b", owner="a")
        with patch("apps.integrations.views.GitHubAppClient") as mock_client:
            mock_client.return_value.list_issues.return_value = [
                {"id": 1, "number": 1, "title": "Issue", "state": "open", "body": "", "labels": [], "html_url": "http://x"},
            ]
            resp = client.post(f"/api/github/repos/{repo.id}/import_issues/", {"state": "open"})
            assert resp.status_code == 200
            assert resp.data["imported"] == 1


@pytest.mark.django_db
class TestGitHubIssueLinkViewSet:
    def test_list_links(self, auth_client):
        client, user = auth_client
        task = Task.objects.create(owner=user, title="T")
        inst = GitHubInstallation.objects.create(user=user, installation_id=1)
        repo = GitHubRepo.objects.create(installation=inst, repo_id=1, full_name="a/b", name="b", owner="a")
        GitHubIssueLink.objects.create(task=task, repo=repo, issue_number=1, issue_id=100)
        resp = client.get("/api/github/links/")
        assert resp.status_code == 200
        assert len(resp.data) == 1

    def test_create_for_task(self, auth_client):
        client, user = auth_client
        task = Task.objects.create(owner=user, title="T")
        inst = GitHubInstallation.objects.create(user=user, installation_id=1)
        repo = GitHubRepo.objects.create(installation=inst, repo_id=1, full_name="a/b", name="b", owner="a")
        link = GitHubIssueLink.objects.create(task=task, repo=repo, issue_number=1, issue_id=100)
        link.delete()  # la tarea no debe tener link para poder crear
        with patch("apps.integrations.views.create_issue_for_task", return_value=link):
            resp = client.post("/api/github/links/create_for_task/", {"task_id": task.id, "repo_id": repo.id})
            assert resp.status_code == 201

    def test_create_for_task_already_linked(self, auth_client):
        client, user = auth_client
        task = Task.objects.create(owner=user, title="T")
        inst = GitHubInstallation.objects.create(user=user, installation_id=1)
        repo = GitHubRepo.objects.create(installation=inst, repo_id=1, full_name="a/b", name="b", owner="a")
        GitHubIssueLink.objects.create(task=task, repo=repo, issue_number=1, issue_id=100)
        resp = client.post("/api/github/links/create_for_task/", {"task_id": task.id, "repo_id": repo.id})
        assert resp.status_code == 400

    def test_create_for_task_not_found(self, auth_client):
        client, user = auth_client
        inst = GitHubInstallation.objects.create(user=user, installation_id=1)
        repo = GitHubRepo.objects.create(installation=inst, repo_id=1, full_name="a/b", name="b", owner="a")
        resp = client.post("/api/github/links/create_for_task/", {"task_id": 999, "repo_id": repo.id})
        assert resp.status_code == 404


@pytest.mark.django_db
class TestGitHubPullRequestViewSet:
    def test_link_task(self, auth_client):
        client, user = auth_client
        inst = GitHubInstallation.objects.create(user=user, installation_id=1)
        repo = GitHubRepo.objects.create(installation=inst, repo_id=1, full_name="a/b", name="b", owner="a")
        pr = GitHubPullRequest.objects.create(repo=repo, pr_number=1, pr_id=100, title="PR")
        task = Task.objects.create(owner=user, title="T")
        resp = client.post(f"/api/github/prs/{pr.id}/link_task/", {"task_id": task.id})
        assert resp.status_code == 200
        assert task in pr.tasks.all()

    def test_link_task_not_found(self, auth_client):
        client, user = auth_client
        inst = GitHubInstallation.objects.create(user=user, installation_id=1)
        repo = GitHubRepo.objects.create(installation=inst, repo_id=1, full_name="a/b", name="b", owner="a")
        pr = GitHubPullRequest.objects.create(repo=repo, pr_number=1, pr_id=100, title="PR")
        resp = client.post(f"/api/github/prs/{pr.id}/link_task/", {"task_id": 999})
        assert resp.status_code == 404


@pytest.mark.django_db
class TestGitHubReleaseViewSet:
    def test_progress(self, auth_client):
        client, user = auth_client
        inst = GitHubInstallation.objects.create(user=user, installation_id=1)
        repo = GitHubRepo.objects.create(installation=inst, repo_id=1, full_name="a/b", name="b", owner="a")
        release = GitHubRelease.objects.create(repo=repo, release_id=1, tag_name="v1.0")
        t1 = Task.objects.create(owner=user, title="T1", state="completed")
        t2 = Task.objects.create(owner=user, title="T2", state="pending")
        release.tasks.add(t1, t2)
        resp = client.get(f"/api/github/releases/{release.id}/progress/")
        assert resp.status_code == 200
        assert resp.data["tasks_total"] == 2
        assert resp.data["tasks_done"] == 1
        assert resp.data["progress_pct"] == 50.0


@pytest.mark.django_db
class TestOAuthViews:
    def test_oauth_providers(self, api_client):
        with override_settings(GITHUB_APP_CLIENT_ID="cid"):
            resp = api_client.get("/api/auth/oauth-providers/")
            assert resp.status_code == 200
            assert resp.data["github"] is True

    def test_github_oauth_start(self, api_client):
        with override_settings(GITHUB_APP_CLIENT_ID="cid", DJANGO_FRONTEND_URL="http://localhost:5173"):
            resp = api_client.get("/api/auth/github/start/")
            assert resp.status_code == 200
            assert "auth_url" in resp.data
            assert "state" in resp.data

    def test_github_oauth_callback_invalid_state(self, api_client):
        resp = api_client.post("/api/auth/github/callback/", {"code": "c", "state": "s"})
        assert resp.status_code == 400


@pytest.mark.django_db
class TestWebhookViews:
    def test_github_webhook_invalid_signature(self, api_client):
        with override_settings(GITHUB_APP_WEBHOOK_SECRET="secret"):
            resp = api_client.post("/api/webhooks/github/", data={}, content_type="application/json", HTTP_X_HUB_SIGNATURE_256="invalid")
            assert resp.status_code == 401

    def test_github_webhook_valid(self, api_client):
        with override_settings(GITHUB_APP_WEBHOOK_SECRET="secret"):
            payload = {"action": "opened", "repository": {"full_name": "a/b"}}
            body = json.dumps(payload).encode()
            signature = "sha256=" + hmac.new(b"secret", body, hashlib.sha256).hexdigest()
            with patch("apps.integrations.webhook_processor.process_webhook_delivery", return_value=({"status": "ok"}, 200)):
                resp = api_client.post(
                    "/api/webhooks/github/",
                    data=body,
                    content_type="application/json",
                    HTTP_X_HUB_SIGNATURE_256=signature,
                    HTTP_X_GITHUB_EVENT="issues",
                    HTTP_X_GITHUB_DELIVERY="d1",
                )
                assert resp.status_code == 200

    def test_webhook_deliveries(self, auth_client):
        client, user = auth_client
        inst = GitHubInstallation.objects.create(user=user, installation_id=1)
        GitHubRepo.objects.create(installation=inst, repo_id=1, full_name="a/b", name="b", owner="a")
        WebhookDelivery.objects.create(delivery_id="d1", event_type="issues", action="opened", repo_full_name="a/b", payload={})
        WebhookDelivery.objects.create(delivery_id="d2", event_type="issues", action="opened", repo_full_name="other/repo", payload={})
        resp = client.get("/api/webhooks/deliveries/")
        assert resp.status_code == 200
        assert len(resp.data) == 1
        assert resp.data[0]["delivery_id"] == "d1"

    def test_webhook_retry_dead_letter(self, auth_client):
        client, user = auth_client
        inst = GitHubInstallation.objects.create(user=user, installation_id=1)
        GitHubRepo.objects.create(installation=inst, repo_id=1, full_name="a/b", name="b", owner="a")
        with patch("apps.integrations.webhook_processor.retry_dead_letter_deliveries", return_value="ok"):
            resp = client.post("/api/webhooks/retry-dead-letter/")
            assert resp.status_code == 200
            assert resp.data["message"] == "ok"

    def test_webhook_retry_dead_letter_no_repos(self, auth_client):
        """Sin repos configurados retorna 404."""
        client, _ = auth_client
        resp = client.post("/api/webhooks/retry-dead-letter/")
        assert resp.status_code == 404
