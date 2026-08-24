"""Tests de integración con GitHub (con API mockeada)."""
import json
import pytest
from unittest.mock import patch, MagicMock

from apps.tasks.models import Task
from apps.integrations.models import GitHubInstallation, GitHubRepo, GitHubIssueLink
from apps.integrations.sync_service import (
    create_issue_for_task,
    import_issue_as_task,
    sync_issue_to_task,
    sync_task_to_issue,
    sync_repo_issues,
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
        is_private=False,
    )


@pytest.mark.django_db
class TestGitHubInstallation:
    def test_listar_instalaciones(self, authed_client, github_installation):
        resp = authed_client.get("/api/github/installations/")
        assert resp.status_code == 200
        assert len(resp.data) == 1
        assert resp.data[0]["account_login"] == "testuser"

    def test_no_ve_instalaciones_ajenas(self, authed_client, other_user):
        GitHubInstallation.objects.create(
            user=other_user,
            installation_id=99999,
            account_login="other",
        )
        resp = authed_client.get("/api/github/installations/")
        assert resp.status_code == 200
        assert len(resp.data) == 0


@pytest.mark.django_db
class TestGitHubRepos:
    def test_listar_repos(self, authed_client, github_repo):
        resp = authed_client.get("/api/github/installations/repos/")
        assert resp.status_code == 200
        assert len(resp.data) == 1
        assert resp.data[0]["full_name"] == "testuser/my-repo"

    @patch("apps.integrations.views.GitHubAppClient")
    def test_descubrir_repos(self, mock_client_class, authed_client, github_installation):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.list_installation_repos.return_value = [
            {
                "id": 200,
                "full_name": "testuser/new-repo",
                "name": "new-repo",
                "owner": {"login": "testuser"},
                "private": False,
                "default_branch": "main",
            }
        ]

        resp = authed_client.post("/api/github/installations/discover_repos/")
        assert resp.status_code == 200
        assert resp.data["total"] == 1
        assert resp.data["new"] == 1
        assert GitHubRepo.objects.filter(full_name="testuser/new-repo").exists()

    def test_toggle_sync(self, authed_client, github_repo):
        resp = authed_client.patch(
            f"/api/github/repos/{github_repo.id}/",
            {"sync_enabled": False},
            format="json",
        )
        assert resp.status_code == 200
        github_repo.refresh_from_db()
        assert github_repo.sync_enabled is False


@pytest.mark.django_db
class TestImportIssues:
    @patch("apps.integrations.views.GitHubAppClient")
    def test_importar_issues(self, mock_client_class, authed_client, github_repo, user):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.list_issues.return_value = [
            {
                "id": 1001,
                "number": 1,
                "title": "Bug en login",
                "state": "open",
                "html_url": "https://github.com/testuser/my-repo/issues/1",
                "body": "Descripción del bug",
                "labels": [],
            },
            {
                "id": 1002,
                "number": 2,
                "title": "Feature request",
                "state": "open",
                "html_url": "https://github.com/testuser/my-repo/issues/2",
                "body": "Nueva feature",
                "labels": [{"name": "enhancement"}],
            },
        ]

        resp = authed_client.post(
            f"/api/github/repos/{github_repo.id}/import_issues/",
            {"state": "open"},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["imported"] == 2
        assert resp.data["skipped"] == 0

        tasks = Task.objects.filter(owner=user)
        assert tasks.count() == 2
        assert GitHubIssueLink.objects.count() == 2

    @patch("apps.integrations.views.GitHubAppClient")
    def test_no_duplicar_import(self, mock_client_class, authed_client, github_repo, user):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.list_issues.return_value = [
            {
                "id": 1001,
                "number": 1,
                "title": "Bug en login",
                "state": "open",
                "html_url": "https://github.com/testuser/my-repo/issues/1",
                "body": "",
                "labels": [],
            }
        ]

        # Primera importación
        authed_client.post(
            f"/api/github/repos/{github_repo.id}/import_issues/",
            {"state": "open"},
            format="json",
        )
        # Segunda importación: debe skip
        resp = authed_client.post(
            f"/api/github/repos/{github_repo.id}/import_issues/",
            {"state": "open"},
            format="json",
        )
        assert resp.data["imported"] == 0
        assert resp.data["skipped"] == 1


@pytest.mark.django_db
class TestSyncBidirectional:
    @patch("apps.integrations.sync_service.GitHubAppClient")
    def test_crear_issue_para_tarea(self, mock_client_class, user, github_repo):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.create_issue.return_value = {
            "id": 5001,
            "number": 42,
            "html_url": "https://github.com/testuser/my-repo/issues/42",
            "state": "open",
        }

        task = Task.objects.create(owner=user, title="Nueva tarea")
        link = create_issue_for_task(task, github_repo)

        assert link.issue_number == 42
        assert link.issue_url == "https://github.com/testuser/my-repo/issues/42"
        assert link.issue_state == "open"
        mock_client.create_issue.assert_called_once()

    @patch("apps.integrations.sync_service.GitHubAppClient")
    def test_sync_issue_a_tarea(self, mock_client_class, user, github_repo):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.update_issue.return_value = {"state": "closed"}

        task = Task.objects.create(owner=user, title="Tarea original", state=Task.State.PENDING)
        link = GitHubIssueLink.objects.create(
            task=task,
            repo=github_repo,
            issue_number=10,
            issue_id=100,
            issue_url="https://github.com/testuser/my-repo/issues/10",
            issue_state="open",
        )

        issue_data = {
            "number": 10,
            "title": "Título actualizado",
            "state": "closed",
            "html_url": "https://github.com/testuser/my-repo/issues/10",
        }
        sync_issue_to_task(link, issue_data)

        task.refresh_from_db()
        assert task.title == "Título actualizado"
        assert task.state == Task.State.COMPLETED
        assert task.completed_at is not None

    @patch("apps.integrations.sync_service.GitHubAppClient")
    def test_completar_tarea_cierra_issue(self, mock_client_class, user, github_repo):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.update_issue.return_value = {"state": "closed"}

        task = Task.objects.create(owner=user, title="Tarea con issue", state=Task.State.PENDING)
        GitHubIssueLink.objects.create(
            task=task,
            repo=github_repo,
            issue_number=5,
            issue_id=50,
            issue_url="https://github.com/testuser/my-repo/issues/5",
            issue_state="open",
        )

        # Completar la tarea
        task.state = Task.State.COMPLETED
        task.save()  # dispara signal → sync_task_to_issue

        mock_client.update_issue.assert_called_once()
        call_kwargs = mock_client.update_issue.call_args
        assert call_kwargs[1]["state"] == "closed" or call_kwargs.kwargs.get("state") == "closed"


@pytest.mark.django_db
class TestWebhook:
    def test_webhook_firma_invalida(self, api_client):
        resp = api_client.post(
            "/api/webhooks/github/",
            data=json.dumps({"action": "opened"}),
            content_type="application/json",
        )
        assert resp.status_code == 401

    @patch("apps.integrations.views.GitHubAppClient.verify_webhook_signature", return_value=True)
    def test_webhook_issue_opened(self, mock_verify, api_client, github_repo, user):
        payload = {
            "action": "opened",
            "issue": {
                "id": 2001,
                "number": 99,
                "title": "Nuevo issue desde GitHub",
                "state": "open",
                "html_url": "https://github.com/testuser/my-repo/issues/99",
                "body": "Descripción",
            },
            "repository": {"full_name": "testuser/my-repo"},
        }
        resp = api_client.post(
            "/api/webhooks/github/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_GITHUB_EVENT="issues",
        )
        assert resp.status_code == 200
        assert "imported" in resp.data["message"]
        # Verificar tarea creada
        assert Task.objects.filter(title="Nuevo issue desde GitHub").exists()

    @patch("apps.integrations.views.GitHubAppClient.verify_webhook_signature", return_value=True)
    def test_webhook_issue_closed_syncs(self, mock_verify, api_client, github_repo, user):
        task = Task.objects.create(owner=user, title="Tarea existente", state=Task.State.PENDING)
        GitHubIssueLink.objects.create(
            task=task,
            repo=github_repo,
            issue_number=7,
            issue_id=70,
            issue_url="https://github.com/testuser/my-repo/issues/7",
            issue_state="open",
        )

        payload = {
            "action": "closed",
            "issue": {
                "number": 7,
                "title": "Tarea existente",
                "state": "closed",
                "html_url": "https://github.com/testuser/my-repo/issues/7",
            },
            "repository": {"full_name": "testuser/my-repo"},
        }
        resp = api_client.post(
            "/api/webhooks/github/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_GITHUB_EVENT="issues",
        )
        assert resp.status_code == 200
        task.refresh_from_db()
        assert task.state == Task.State.COMPLETED


@pytest.mark.django_db
class TestOAuthFlow:
    @patch("apps.integrations.views.GitHubOAuthClient")
    def test_oauth_start(self, mock_oauth_class, api_client):
        mock_oauth = MagicMock()
        mock_oauth_class.return_value = mock_oauth
        mock_oauth.get_authorize_url.return_value = "https://github.com/login/oauth/authorize?client_id=test"

        resp = api_client.get("/api/auth/github/start/")
        assert resp.status_code == 200
        assert "auth_url" in resp.data
        assert "github.com" in resp.data["auth_url"]

    @patch("apps.integrations.views.GitHubOAuthClient")
    def test_oauth_callback(self, mock_oauth_class, api_client):
        # Configurar session
        api_client.handler._enforce_csrf_checks = False
        session = api_client.session
        session["github_oauth_state"] = "test-state"
        session.save()

        mock_oauth = MagicMock()
        mock_oauth_class.return_value = mock_oauth
        mock_oauth.exchange_code.return_value = {"access_token": "gho_test123"}
        mock_oauth.get_user_info.return_value = {
            "id": 11111,
            "login": "ghuser",
            "email": "ghuser@example.com",
            "avatar_url": "https://github.com/avatars/11111.png",
        }

        resp = api_client.post(
            "/api/auth/github/callback/",
            {"code": "test-code", "state": "test-state"},
            format="json",
        )
        assert resp.status_code == 200
        assert "access" in resp.data
        assert resp.data["github_username"] == "ghuser"

        # Verificar instalación creada
        from django.contrib.auth import get_user_model
        User = get_user_model()
        u = User.objects.get(email="ghuser@example.com")
        assert GitHubInstallation.objects.filter(user=u).exists()
