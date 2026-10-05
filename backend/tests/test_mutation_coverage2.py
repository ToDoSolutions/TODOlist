"""Tests para matar mutantes sobrevivientes de la segunda ronda de mutmut.

Targets:
- integrations/views.py: response keys, defaults, viewset attrs, webhook, oauth
- automations/engine.py: condition defaults, action defaults, serialize_context
- offline_sync/services.py: response keys, _filter_task_fields, _task_to_dict, export
"""
import json
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone

from apps.automations.engine import (
    _serialize_context,
    evaluate_conditions,
    execute_action,
    run_daily_checks,
    trigger_automation,
)
from apps.automations.models import AutomationLog, AutomationRule
from apps.integrations import views as integrations_views
from apps.integrations.models import (
    GitHubInstallation,
    GitHubPullRequest,
    GitHubRelease,
    GitHubRepo,
    WebhookDelivery,
)
from apps.notifications.models import Notification
from apps.offline_sync.models import SyncDevice, SyncOperation
from apps.offline_sync.services import (
    _filter_task_fields,
    _task_to_dict,
    apply_sync_operations,
    get_changes_since,
    register_device,
)
from apps.tasks.models import Sprint, Task

User = get_user_model()


# ============================================================================
# integrations/views.py — matar mutantes 366-374, 388-396, 407
# ============================================================================

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
class TestDiscoverReposMutationKills:
    """Mata mutantes 366-368, 373-374: default_branch, created += 1, response keys."""

    @patch("apps.integrations.views.GitHubAppClient")
    def test_discover_repos_multiple_new_counts_created(self, mock_client_class, authed_client, github_installation):
        """created se acumula con múltiples repos nuevos (mata created=1)."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.list_installation_repos.return_value = [
            {"id": 1, "full_name": "t/r1", "name": "r1", "owner": {"login": "t"}, "private": False, "default_branch": "main"},
            {"id": 2, "full_name": "t/r2", "name": "r2", "owner": {"login": "t"}, "private": False, "default_branch": "main"},
            {"id": 3, "full_name": "t/r3", "name": "r3", "owner": {"login": "t"}, "private": False, "default_branch": "main"},
        ]
        resp = authed_client.post("/api/github/installations/discover_repos/")
        assert resp.status_code == 200
        assert resp.data["new"] == 3  # Si created=1, sería 1
        assert resp.data["total"] == 3

    @patch("apps.integrations.views.GitHubAppClient")
    def test_discover_repos_default_branch_from_api(self, mock_client_class, authed_client, github_installation):
        """default_branch se toma del API, no del default 'main'."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.list_installation_repos.return_value = [
            {"id": 200, "full_name": "t/r", "name": "r", "owner": {"login": "t"}, "private": False, "default_branch": "develop"},
        ]
        resp = authed_client.post("/api/github/installations/discover_repos/")
        assert resp.status_code == 200
        repo = GitHubRepo.objects.get(repo_id=200)
        assert repo.default_branch == "develop"  # No "main"

    @patch("apps.integrations.views.GitHubAppClient")
    def test_discover_repos_default_branch_fallback_main(self, mock_client_class, authed_client, github_installation):
        """default_branch sin clave usa 'main' como default."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.list_installation_repos.return_value = [
            {"id": 201, "full_name": "t/r2", "name": "r2", "owner": {"login": "t"}, "private": False},
        ]
        resp = authed_client.post("/api/github/installations/discover_repos/")
        assert resp.status_code == 200
        repo = GitHubRepo.objects.get(repo_id=201)
        assert repo.default_branch == "main"

    @patch("apps.integrations.views.GitHubAppClient")
    def test_discover_repos_response_keys_and_message(self, mock_client_class, authed_client, github_installation):
        """Verifica keys exactas y contenido del message."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.list_installation_repos.return_value = [
            {"id": 300, "full_name": "t/a", "name": "a", "owner": {"login": "t"}, "private": False, "default_branch": "main"},
            {"id": 301, "full_name": "t/b", "name": "b", "owner": {"login": "t"}, "private": False, "default_branch": "main"},
        ]
        resp = authed_client.post("/api/github/installations/discover_repos/")
        assert resp.status_code == 200
        assert set(resp.data.keys()) == {"total", "new", "message"}
        assert resp.data["message"] == "Se encontraron 2 repos, 2 nuevos"


@pytest.mark.django_db
class TestImportIssuesMutationKills:
    """Mata mutantes 388-396, 407: is_valid, state default, pull_request filter, skipped."""

    @patch("apps.integrations.views.GitHubAppClient")
    def test_import_issues_default_state_open(self, mock_client_class, authed_client, github_repo, user):
        """import_issues sin state usa 'open' por defecto."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        # El cliente recibe state="open" por defecto
        mock_client.list_issues.return_value = [
            {"id": 1, "number": 1, "title": "Issue 1", "state": "open",
             "html_url": "http://gh/1", "body": "", "labels": []},
        ]
        resp = authed_client.post(
            f"/api/github/repos/{github_repo.id}/import_issues/",
            {}, format="json",
        )
        assert resp.status_code == 200
        # Verifica que se llamó con state="open"
        mock_client.list_issues.assert_called_once_with(github_repo.owner, github_repo.name, state="open")

    @patch("apps.integrations.views.GitHubAppClient")
    def test_import_issues_invalid_data_returns_400(self, mock_client_class, authed_client, github_repo):
        """import_issues con datos inválidos devuelve 400 (is_valid raise_exception=True)."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        # Enviar state inválido (ImportIssuesSerializer puede validar choices)
        resp = authed_client.post(
            f"/api/github/repos/{github_repo.id}/import_issues/",
            {"state": "invalid_state_value"},
            format="json",
        )
        # Si is_valid(raise_exception=True) funciona, devuelve 400
        assert resp.status_code == 400

    @patch("apps.integrations.views.GitHubAppClient")
    def test_import_issues_filters_prs(self, mock_client_class, authed_client, github_repo, user):
        """import_issues filtra PRs (tienen 'pull_request' key)."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.list_issues.return_value = [
            {"id": 1, "number": 1, "title": "Issue", "state": "open",
             "html_url": "http://gh/1", "body": "", "labels": []},
            {"id": 2, "number": 2, "title": "PR", "state": "open",
             "html_url": "http://gh/2", "body": "", "labels": [],
             "pull_request": {"url": "..."}},
        ]
        resp = authed_client.post(
            f"/api/github/repos/{github_repo.id}/import_issues/",
            {}, format="json",
        )
        assert resp.status_code == 200
        assert resp.data["total"] == 1  # PR filtrado

    @patch("apps.integrations.views.import_issue_as_task")
    @patch("apps.integrations.views.GitHubAppClient")
    def test_import_issues_skipped_accumulates(self, mock_client_class, mock_import, authed_client, github_repo, user):
        """skipped se acumula con múltiples issues ya importados (mata skipped=1)."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.list_issues.return_value = [
            {"id": 1, "number": 1, "title": "I1", "state": "open", "html_url": "u1", "body": "", "labels": []},
            {"id": 2, "number": 2, "title": "I2", "state": "open", "html_url": "u2", "body": "", "labels": []},
            {"id": 3, "number": 3, "title": "I3", "state": "open", "html_url": "u3", "body": "", "labels": []},
        ]
        # Todos ya existen (created=False)
        mock_import.return_value = (MagicMock(), False)
        resp = authed_client.post(
            f"/api/github/repos/{github_repo.id}/import_issues/",
            {}, format="json",
        )
        assert resp.status_code == 200
        assert resp.data["skipped"] == 3  # Si skipped=1, sería 1
        assert resp.data["imported"] == 0


# ============================================================================
# integrations/views.py — matar mutantes 413-436 (viewset attrs, PR link)
# ============================================================================

@pytest.mark.django_db
class TestViewSetAttributes:
    """Mata mutantes 413, 421, 427, 432-436, 473-476: serializer_class y permission_classes."""

    def test_issue_link_viewset_attrs(self):
        vs = integrations_views.GitHubIssueLinkViewSet()
        assert vs.serializer_class is not None
        assert vs.permission_classes is not None

    def test_pr_viewset_attrs(self):
        vs = integrations_views.GitHubPullRequestViewSet()
        assert vs.serializer_class is not None
        assert vs.permission_classes is not None

    def test_commit_viewset_attrs(self):
        vs = integrations_views.GitHubCommitViewSet()
        assert vs.serializer_class is not None
        assert vs.permission_classes is not None

    def test_release_viewset_attrs(self):
        vs = integrations_views.GitHubReleaseViewSet()
        assert vs.serializer_class is not None
        assert vs.permission_classes is not None

    def test_checkrun_viewset_attrs(self):
        vs = integrations_views.GitHubCheckRunViewSet()
        assert vs.serializer_class is not None
        assert vs.permission_classes is not None


@pytest.mark.django_db
class TestPrLinkTaskMutationKills:
    """Mata mutantes 421, 427: pr = None, response message."""

    def test_link_task_success_message(self, authed_client, github_installation, user):
        """link_task exitoso devuelve mensaje con PR number y task_id."""
        repo = GitHubRepo.objects.create(
            installation=github_installation, repo_id=1,
            full_name="t/r", name="r", owner="t",
        )
        pr = GitHubPullRequest.objects.create(
            repo=repo, pr_number=42, pr_id=1, title="PR 1", state="open",
            html_url="http://gh/1", is_merged=False,
        )
        task = Task.objects.create(owner=user, title="T")
        resp = authed_client.post(
            f"/api/github/prs/{pr.id}/link_task/",
            {"task_id": task.id},
            format="json",
        )
        assert resp.status_code == 200
        assert "message" in resp.data
        assert "42" in resp.data["message"]
        assert str(task.id) in resp.data["message"]


# ============================================================================
# integrations/views.py — matar mutantes 448-467 (release progress)
# ============================================================================

@pytest.mark.django_db
class TestReleaseProgressMutationKills:
    """Mata mutantes 448, 456-457, 463, 465-467: prs_merged, prs_pending, progress_pct."""

    def _create_release_with_data(self, github_installation, user, total_tasks, done_tasks, merged_prs, total_prs):
        repo = GitHubRepo.objects.create(
            installation=github_installation, repo_id=1,
            full_name="t/r", name="r", owner="t",
        )
        release = GitHubRelease.objects.create(
            repo=repo, release_id=1, tag_name="v1.0", name="v1.0",
            html_url="http://gh/v1.0",
            state=GitHubRelease.ReleaseState.PUBLISHED,
            is_prerelease=False, published_at=timezone.now(),
        )
        for i in range(done_tasks):
            t = Task.objects.create(owner=user, title=f"Done {i}", state="completed")
            release.tasks.add(t)
        for i in range(total_tasks - done_tasks):
            t = Task.objects.create(owner=user, title=f"Pending {i}", state="pending")
            release.tasks.add(t)
        for i in range(merged_prs):
            pr = GitHubPullRequest.objects.create(
                repo=repo, pr_number=i + 1, pr_id=i + 100, title=f"Merged {i}",
                state="closed", html_url=f"http://gh/{i}", is_merged=True,
            )
            release.pull_requests.add(pr)
        for i in range(total_prs - merged_prs):
            pr = GitHubPullRequest.objects.create(
                repo=repo, pr_number=i + 100, pr_id=i + 200, title=f"Open {i}",
                state="open", html_url=f"http://gh/o{i}", is_merged=False,
            )
            release.pull_requests.add(pr)
        return release

    def test_progress_exact_values(self, authed_client, github_installation, user):
        """Verifica valores exactos de prs_merged, prs_pending, progress_pct."""
        release = self._create_release_with_data(github_installation, user, 4, 1, 2, 3)
        resp = authed_client.get(f"/api/github/releases/{release.id}/progress/")
        assert resp.status_code == 200
        assert resp.data["tasks_total"] == 4
        assert resp.data["tasks_done"] == 1
        assert resp.data["tasks_pending"] == 3
        assert resp.data["prs_total"] == 3
        assert resp.data["prs_merged"] == 2  # is_merged=True, no False
        assert resp.data["prs_pending"] == 1  # 3 - 2 = 1, no 3 + 2
        assert resp.data["progress_pct"] == 25.0  # 1/4*100 = 25.0

    def test_progress_single_task_boundary(self, authed_client, github_installation, user):
        """total=1 debe dar progress_pct=100 si done=1 (mata total > 1)."""
        release = self._create_release_with_data(github_installation, user, 1, 1, 0, 0)
        resp = authed_client.get(f"/api/github/releases/{release.id}/progress/")
        assert resp.status_code == 200
        assert resp.data["progress_pct"] == 100.0  # Si total > 1, sería 0

    def test_progress_rounding_one_decimal(self, authed_client, github_installation, user):
        """progress_pct se redondea a 1 decimal (mata round(..., 2))."""
        release = self._create_release_with_data(github_installation, user, 3, 1, 0, 0)
        resp = authed_client.get(f"/api/github/releases/{release.id}/progress/")
        assert resp.status_code == 200
        # 1/3*100 = 33.333... → round(..., 1) = 33.3, round(..., 2) = 33.33
        assert resp.data["progress_pct"] == 33.3


# ============================================================================
# integrations/views.py — matar mutantes 481-487 (oauth_providers)
# ============================================================================

@pytest.mark.django_db
class TestOAuthProvidersMutationKills:
    """Mata mutantes 481-487: settings keys."""

    @override_settings(GITHUB_APP_CLIENT_ID="gh_test_id")
    def test_oauth_providers_response_keys(self, api_client):
        """Verifica que la respuesta tiene 'github' y 'google' keys."""
        resp = api_client.get("/api/auth/oauth-providers/")
        assert resp.status_code == 200
        assert "github" in resp.data
        assert "google" in resp.data
        assert resp.data["github"] is True


# ============================================================================
# integrations/views.py — matar mutantes 505-510 (oauth callback errors)
# ============================================================================

@pytest.mark.django_db
class TestOAuthCallbackMutationKills:
    """Mata mutantes 505-510: error message content, redirect_uri."""

    def test_oauth_callback_no_code_error_message(self, api_client):
        """callback sin code devuelve error con mensaje exacto."""
        session = api_client.session
        session["github_oauth_state"] = "state"
        session.save()
        resp = api_client.post("/api/auth/github/callback/", {"state": "state"}, format="json")
        assert resp.status_code == 400
        assert resp.data["error"] == "Parámetros OAuth inválidos"

    def test_oauth_callback_state_mismatch_error_message(self, api_client):
        """callback con state mismatch devuelve error con mensaje exacto."""
        session = api_client.session
        session["github_oauth_state"] = "stored"
        session.save()
        resp = api_client.post(
            "/api/auth/github/callback/",
            {"code": "c", "state": "different"},
            format="json",
        )
        assert resp.status_code == 400
        assert resp.data["error"] == "Parámetros OAuth inválidos"


# ============================================================================
# integrations/views.py — matar mutantes 520-539 (oauth user creation)
# ============================================================================

@pytest.mark.django_db
class TestOAuthCallbackUserCreationKills:
    """Mata mutantes 520, 524-525, 527, 531, 536, 538-539."""

    @patch("apps.integrations.views.GitHubOAuthClient")
    def test_oauth_callback_new_user_response_keys(self, mock_oauth_class, api_client):
        """Verifica keys exactas en respuesta de callback con usuario nuevo."""
        session = api_client.session
        session["github_oauth_state"] = "s"
        session.save()
        mock_oauth = MagicMock()
        mock_oauth_class.return_value = mock_oauth
        mock_oauth.exchange_code.return_value = {"access_token": "tok"}
        mock_oauth.get_user_info.return_value = {
            "id": 11111, "login": "newuser", "email": "new@test.com",
            "avatar_url": "http://avatar",
        }
        # Email verificado → la cuenta se crea con el email real
        mock_oauth.get_verified_emails.return_value = {"new@test.com"}
        resp = api_client.post(
            "/api/auth/github/callback/",
            {"code": "c", "state": "s"},
            format="json",
        )
        assert resp.status_code == 200
        # Verifica keys exactas
        assert "access" in resp.data
        assert "refresh" in resp.data
        assert "user" in resp.data
        assert "id" in resp.data["user"]
        assert "email" in resp.data["user"]
        assert "username" in resp.data["user"]
        assert "github_username" in resp.data
        assert resp.data["github_username"] == "newuser"
        assert resp.data["user"]["email"] == "new@test.com"
        assert resp.data["user"]["username"] == "newuser"

    @patch("apps.integrations.views.GitHubOAuthClient")
    def test_oauth_callback_installation_fields(self, mock_oauth_class, api_client):
        """Verifica que la instalación se crea con account_type='User' y avatar_url."""
        session = api_client.session
        session["github_oauth_state"] = "s"
        session.save()
        mock_oauth = MagicMock()
        mock_oauth_class.return_value = mock_oauth
        mock_oauth.exchange_code.return_value = {"access_token": "tok"}
        mock_oauth.get_user_info.return_value = {
            "id": 22222, "login": "avatartest", "email": "av@test.com",
            "avatar_url": "http://avatar.png",
        }
        resp = api_client.post(
            "/api/auth/github/callback/",
            {"code": "c", "state": "s"},
            format="json",
        )
        assert resp.status_code == 200
        inst = GitHubInstallation.objects.get(github_user_id=22222)
        assert inst.account_type == "User"  # No "XXUserXX"
        assert inst.avatar_url == "http://avatar.png"  # No default ""
        assert inst.account_login == "avatartest"

    @patch("apps.integrations.views.GitHubOAuthClient")
    def test_oauth_callback_login_value_preserved(self, mock_oauth_class, api_client):
        """login con valor se preserva en github_username."""
        session = api_client.session
        session["github_oauth_state"] = "s"
        session.save()
        mock_oauth = MagicMock()
        mock_oauth_class.return_value = mock_oauth
        mock_oauth.exchange_code.return_value = {"access_token": "tok"}
        mock_oauth.get_user_info.return_value = {
            "id": 33333, "login": "mylogin", "email": "login@test.com",
            "avatar_url": "http://av",
        }
        resp = api_client.post(
            "/api/auth/github/callback/",
            {"code": "c", "state": "s"},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["github_username"] == "mylogin"
        inst = GitHubInstallation.objects.get(github_user_id=33333)
        assert inst.github_username == "mylogin"
        assert inst.account_login == "mylogin"


# ============================================================================
# integrations/views.py — matar mutantes 544-572 (webhook)
# ============================================================================

@pytest.mark.django_db
class TestWebhookMutationKills:
    """Mata mutantes 544-572: signature, event headers, payload keys."""

    def test_webhook_invalid_signature_error_message(self, api_client):
        """Webhook con firma inválida devuelve error exacto."""
        resp = api_client.post(
            "/api/webhooks/github/",
            data=json.dumps({"action": "opened"}),
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256="sha256=invalid",
        )
        assert resp.status_code == 401
        assert resp.data["error"] == "Firma inválida"

    @patch("apps.integrations.webhook_processor.process_webhook_delivery")
    @patch("apps.integrations.views.GitHubAppClient.verify_webhook_signature", return_value=True)
    def test_webhook_valid_passes_headers(self, mock_verify, mock_process, api_client):
        """Webhook válido pasa event_type, delivery_id, action, repo_full_name."""
        mock_process.return_value = ({"ok": True}, 200)
        payload = {"action": "opened", "repository": {"full_name": "test/repo"}}
        resp = api_client.post(
            "/api/webhooks/github/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_GITHUB_EVENT="pull_request",
            HTTP_X_GITHUB_DELIVERY="delivery-123",
        )
        assert resp.status_code == 200
        mock_process.assert_called_once()
        call_kwargs = mock_process.call_args.kwargs
        assert call_kwargs["event_type"] == "pull_request"
        assert call_kwargs["delivery_id"] == "delivery-123"
        assert call_kwargs["action"] == "opened"
        assert call_kwargs["repo_full_name"] == "test/repo"

    @patch("apps.integrations.webhook_processor.process_webhook_delivery")
    @patch("apps.integrations.views.GitHubAppClient.verify_webhook_signature", return_value=True)
    def test_webhook_missing_action_default_empty(self, mock_verify, mock_process, api_client):
        """Webhook sin action en payload usa default ''."""
        mock_process.return_value = ({"ok": True}, 200)
        payload = {"repository": {"full_name": "test/repo"}}
        resp = api_client.post(
            "/api/webhooks/github/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_GITHUB_EVENT="push",
            HTTP_X_GITHUB_DELIVERY="d1",
        )
        assert resp.status_code == 200
        call_kwargs = mock_process.call_args.kwargs
        assert call_kwargs["action"] == ""

    @patch("apps.integrations.webhook_processor.process_webhook_delivery")
    @patch("apps.integrations.views.GitHubAppClient.verify_webhook_signature", return_value=True)
    def test_webhook_missing_repo_default_empty(self, mock_verify, mock_process, api_client):
        """Webhook sin repository.full_name usa default ''."""
        mock_process.return_value = ({"ok": True}, 200)
        payload = {"action": "created"}
        resp = api_client.post(
            "/api/webhooks/github/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_GITHUB_EVENT="issues",
            HTTP_X_GITHUB_DELIVERY="d2",
        )
        assert resp.status_code == 200
        call_kwargs = mock_process.call_args.kwargs
        assert call_kwargs["repo_full_name"] == ""


# ============================================================================
# integrations/views.py — matar mutantes 576, 580, 586 (webhook_deliveries, retry)
# ============================================================================

@pytest.mark.django_db
class TestWebhookDeliveriesMutationKills:
    """Mata mutantes 576, 580, 586: permission, limit 50, retry permission."""

    def test_webhook_deliveries_requires_auth(self, api_client):
        """webhook_deliveries sin auth devuelve 401/403."""
        resp = api_client.get("/api/webhooks/deliveries/")
        assert resp.status_code in (401, 403)

    def test_webhook_deliveries_max_50(self, authed_client, github_installation, github_repo):
        """webhook_deliveries retorna máximo 50 entregas."""
        for i in range(60):
            WebhookDelivery.objects.create(
                delivery_id=f"d{i}", event_type="push",
                action="opened", repo_full_name="testuser/my-repo",
                payload={}, status="delivered",
            )
        resp = authed_client.get("/api/webhooks/deliveries/")
        assert resp.status_code == 200
        assert len(resp.data) == 50  # No 51

    def test_webhook_retry_requires_auth(self, api_client):
        """webhook_retry_dead_letter sin auth devuelve 401/403."""
        resp = api_client.post("/api/webhooks/retry-dead-letter/")
        assert resp.status_code in (401, 403)


# ============================================================================
# automations/engine.py — matar mutantes 3, 9, 11, 26 (evaluate_conditions)
# ============================================================================

class TestEvaluateConditionsMutationKills:
    """Mata mutantes 3, 9, 11, 26: defaults y boundary gt."""

    def test_condition_without_field_uses_empty(self):
        """Condición sin 'field' usa '' como default."""
        # Si field="XXXX", context.get("XXXX","") != "1" → False
        # Si field="", context.get("","") != "1" → True (pass)
        assert evaluate_conditions([{"operator": "not_equals", "value": "1"}], {})

    def test_condition_without_value_uses_empty(self):
        """Condición sin 'value' usa '' como default."""
        # Si value="XXXX", str(actual) != "XXXX" → False (equals fails)
        # Si value="", str(actual) == "" → True (equals passes with empty context)
        assert evaluate_conditions([{"field": "missing", "operator": "equals"}], {})

    def test_condition_without_field_actual_uses_empty(self):
        """Si el field no está en context, actual=''."""
        # field="x" no está en context → actual=""
        # operator=equals, value="" → "" == "" → True
        assert evaluate_conditions([{"field": "x", "operator": "equals", "value": ""}], {})

    def test_gt_boundary_equal_returns_false(self):
        """gt con actual == expected devuelve False (mata >=)."""
        # 5 > 5 is False, but 5 >= 5 is True
        assert not evaluate_conditions(
            [{"field": "p", "operator": "gt", "value": "5"}],
            {"p": "5"},
        )


# ============================================================================
# automations/engine.py — matar mutantes 35-57 (SET_PRIORITY, SET_STATE defaults)
# ============================================================================

@pytest.mark.django_db(transaction=True)
class TestExecuteActionDefaultsMutationKills:
    """Mata mutantes 35-57: defaults de SET_PRIORITY y SET_STATE."""

    def test_set_priority_default_3(self, user, task):
        """SET_PRIORITY sin priority param usa default 3."""
        task.priority = 1
        task.save()
        rule = AutomationRule.objects.create(
            owner=user, name="P", trigger=AutomationRule.Trigger.TASK_CREATED,
            action=AutomationRule.Action.SET_PRIORITY,
            action_params={}, enabled=True,
        )
        result = execute_action(rule, {"task": task, "user": user})
        task.refresh_from_db()
        assert task.priority == 3  # No 4
        assert result["new_priority"] == 3
        assert result["old_priority"] == 1

    def test_set_state_default_pending(self, user, task):
        """SET_STATE sin state param usa default 'pending'."""
        task.state = "in_progress"
        task.save()
        rule = AutomationRule.objects.create(
            owner=user, name="S", trigger=AutomationRule.Trigger.TASK_CREATED,
            action=AutomationRule.Action.SET_STATE,
            action_params={}, enabled=True,
        )
        result = execute_action(rule, {"task": task, "user": user})
        task.refresh_from_db()
        assert task.state == "pending"  # No "XXpendingXX"
        assert result["new_state"] == "pending"
        assert result["old_state"] == "in_progress"

    def test_set_state_result_keys(self, user, task):
        """SET_STATE devuelve 'old_state' y 'new_state' keys."""
        rule = AutomationRule.objects.create(
            owner=user, name="S", trigger=AutomationRule.Trigger.TASK_CREATED,
            action=AutomationRule.Action.SET_STATE,
            action_params={"state": "completed"}, enabled=True,
        )
        result = execute_action(rule, {"task": task, "user": user})
        assert "old_state" in result  # No "XXold_stateXX"
        assert "new_state" in result
        assert result["new_state"] == "completed"


# ============================================================================
# automations/engine.py — matar mutantes 67-88 (CREATE_NOTIFICATION, CREATE_TASK)
# ============================================================================

@pytest.mark.django_db(transaction=True)
class TestCreateNotificationAndTaskMutationKills:
    """Mata mutantes 67-88: notification defaults, task defaults."""

    def test_create_notification_type_and_default_title(self, user, task):
        """CREATE_NOTIFICATION crea notificación con type='automation_triggered' y title default."""
        rule = AutomationRule.objects.create(
            owner=user, name="MyRule", trigger=AutomationRule.Trigger.TASK_CREATED,
            action=AutomationRule.Action.CREATE_NOTIFICATION,
            action_params={}, enabled=True,
        )
        result = execute_action(rule, {"task": task, "user": user})
        assert result["notification_created"] is True
        notif = Notification.objects.filter(recipient=user).first()
        assert notif is not None
        assert notif.type == "automation_triggered"  # No "XXautomation_triggeredXX"
        assert notif.title == "Automatización: MyRule"  # No "XX...XX"

    def test_create_notification_with_sprint(self, user, task, project):
        """CREATE_NOTIFICATION con sprint en context lo pasa a notify."""
        sprint = Sprint.objects.create(
            owner=user, project=project, name="S1",
            state=Sprint.SprintState.PLANNED,
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=14),
        )
        rule = AutomationRule.objects.create(
            owner=user, name="N", trigger=AutomationRule.Trigger.SPRINT_CLOSED,
            action=AutomationRule.Action.CREATE_NOTIFICATION,
            action_params={"title": "Sprint notif", "body": "Body text"},
            enabled=True,
        )
        result = execute_action(rule, {"task": task, "user": user, "sprint": sprint})
        assert result["notification_created"] is True
        notif = Notification.objects.filter(recipient=user).first()
        assert notif.body == "Body text"  # No "XXbodyXX"

    def test_create_task_all_fields(self, user):
        """CREATE_TASK con todos los params verifica valores exactos."""
        # Limpiar reglas que puedan interferir via signals
        AutomationRule.objects.filter(trigger=AutomationRule.Trigger.TASK_CREATED).delete()
        rule = AutomationRule.objects.create(
            owner=user, name="CT", trigger=AutomationRule.Trigger.DAILY_CHECK,
            action=AutomationRule.Action.CREATE_TASK,
            action_params={
                "title": "Custom Task",
                "description": "Custom desc",
                "priority": 1,
                "state": "in_progress",
            },
            enabled=True,
        )
        result = execute_action(rule, {"user": user})
        task = Task.objects.get(id=result["created_task_id"])
        assert task.description == "Custom desc"  # No "XXdescriptionXX"
        assert task.priority == 1  # No default 4
        assert task.state == "in_progress"  # No "XXpendingXX"
        assert result["created_task_id"] == task.id
        assert result["created_task_title"] == "Custom Task"

    def test_create_task_default_priority_3(self, user):
        """CREATE_TASK sin priority usa default 3 (no 4)."""
        AutomationRule.objects.filter(trigger=AutomationRule.Trigger.TASK_CREATED).delete()
        rule = AutomationRule.objects.create(
            owner=user, name="CT", trigger=AutomationRule.Trigger.DAILY_CHECK,
            action=AutomationRule.Action.CREATE_TASK,
            action_params={"title": "Default P"},
            enabled=True,
        )
        result = execute_action(rule, {"user": user})
        task = Task.objects.get(id=result["created_task_id"])
        assert task.priority == 3  # No 4

    def test_create_task_default_state_pending(self, user):
        """CREATE_TASK sin state usa default 'pending'."""
        AutomationRule.objects.filter(trigger=AutomationRule.Trigger.TASK_CREATED).delete()
        rule = AutomationRule.objects.create(
            owner=user, name="CT", trigger=AutomationRule.Trigger.DAILY_CHECK,
            action=AutomationRule.Action.CREATE_TASK,
            action_params={"title": "Default S"},
            enabled=True,
        )
        result = execute_action(rule, {"user": user})
        task = Task.objects.get(id=result["created_task_id"])
        assert task.state == "pending"  # No "XXpendingXX"


# ============================================================================
# automations/engine.py — matar mutantes 97-125 (SET_ASSIGNEE, ADD_TAG)
# ============================================================================

@pytest.mark.django_db(transaction=True)
class TestSetAssigneeAndTagMutationKills:
    """Mata mutantes 97-125: SET_ASSIGNEE y ADD_TAG."""

    def test_set_assignee_by_email(self, user, task):
        """SET_ASSIGNEE por email funciona y devuelve keys correctas."""
        from apps.collaboration.models import ProjectMember
        assignee = User.objects.create_user(
            email="assignee@test.com", username="a1", password="p",
        )
        ProjectMember.objects.create(project=task.project, user=assignee)
        rule = AutomationRule.objects.create(
            owner=user, name="A", trigger=AutomationRule.Trigger.TASK_CREATED,
            action=AutomationRule.Action.SET_ASSIGNEE,
            action_params={"assignee_email": "assignee@test.com"}, enabled=True,
        )
        result = execute_action(rule, {"task": task, "user": user})
        assert "old_assignee" in result  # No "XXold_assigneeXX"
        assert "new_assignee" in result
        assert result["new_assignee"] == "assignee@test.com"
        task.refresh_from_db()
        assert task.assignee == assignee

    def test_set_assignee_by_email_not_found_error(self, user, task):
        """SET_ASSIGNEE por email inexistente devuelve error con email."""
        rule = AutomationRule.objects.create(
            owner=user, name="A", trigger=AutomationRule.Trigger.TASK_CREATED,
            action=AutomationRule.Action.SET_ASSIGNEE,
            action_params={"assignee_email": "nobody@test.com"}, enabled=True,
        )
        result = execute_action(rule, {"task": task, "user": user})
        assert "error" in result
        assert "nobody@test.com" in result["error"]

    def test_set_assignee_old_assignee_value(self, user, task):
        """SET_ASSIGNEE guarda old_assignee correctamente."""
        from apps.collaboration.models import ProjectMember
        old = User.objects.create_user(
            email="old@test.com", username="old", password="p",
        )
        ProjectMember.objects.create(project=task.project, user=old)
        task.assignee = old
        task.save()
        new = User.objects.create_user(
            email="new@test.com", username="new", password="p",
        )
        ProjectMember.objects.create(project=task.project, user=new)
        rule = AutomationRule.objects.create(
            owner=user, name="A", trigger=AutomationRule.Trigger.TASK_CREATED,
            action=AutomationRule.Action.SET_ASSIGNEE,
            action_params={"assignee_id": new.id}, enabled=True,
        )
        result = execute_action(rule, {"task": task, "user": user})
        assert result["old_assignee"] == str(old)  # No None

    def test_add_tag_with_color(self, user, task):
        """ADD_TAG con tag_color crea tag con color especificado."""
        rule = AutomationRule.objects.create(
            owner=user, name="T", trigger=AutomationRule.Trigger.TASK_CREATED,
            action=AutomationRule.Action.ADD_TAG,
            action_params={"tag_name": "urgent", "tag_color": "#ff0000"},
            enabled=True,
        )
        result = execute_action(rule, {"task": task, "user": user})
        assert result["tag_added"] == "urgent"
        assert result["tag_created"] is True
        from apps.tags.models import Tag
        tag = Tag.objects.get(name="urgent", owner=user)
        assert tag.color == "#ff0000"  # No "#1976d2"

    def test_add_tag_default_color(self, user, task):
        """ADD_TAG sin tag_color usa default '#1976d2'."""
        rule = AutomationRule.objects.create(
            owner=user, name="T", trigger=AutomationRule.Trigger.TASK_CREATED,
            action=AutomationRule.Action.ADD_TAG,
            action_params={"tag_name": "defaultcolor"},
            enabled=True,
        )
        execute_action(rule, {"task": task, "user": user})
        from apps.tags.models import Tag
        tag = Tag.objects.get(name="defaultcolor", owner=user)
        assert tag.color == "#1976d2"  # No "XX#1976d2XX"


# ============================================================================
# automations/engine.py — matar mutantes 134-150 (serialize_context)
# ============================================================================

@pytest.mark.django_db
class TestSerializeContextMutationKills:
    """Mata mutantes 134-150: _serialize_context keys y tipos."""

    def test_serialize_django_model(self, user):
        """Serializa un modelo Django con _type, id, str."""
        ctx = {"user": user}
        result = _serialize_context(ctx)
        assert "user" in result
        assert result["user"]["_type"] == "User"  # No "XX_typeXX"
        assert result["user"]["id"] == user.id  # No "XXidXX"
        assert result["user"]["str"] == str(user)  # No "XXstrXX"

    def test_serialize_primitives(self):
        """Serializa primitivos directamente."""
        ctx = {"s": "hello", "i": 42, "f": 3.14, "b": True, "n": None, "l": [1, 2], "d": {"k": "v"}}
        result = _serialize_context(ctx)
        assert result["s"] == "hello"
        assert result["i"] == 42
        assert result["f"] == 3.14
        assert result["b"] is True
        assert result["n"] is None
        assert result["l"] == [1, 2]
        assert result["d"] == {"k": "v"}

    def test_serialize_other_to_str(self):
        """Serializa objetos no-modelo ni primitivos como str()."""

        class Custom:
            def __str__(self):
                return "custom"

        ctx = {"obj": Custom()}
        result = _serialize_context(ctx)
        assert result["obj"] == "custom"


# ============================================================================
# automations/engine.py — matar mutantes 160-169 (trigger_automation)
# ============================================================================

@pytest.mark.django_db(transaction=True)
class TestTriggerAutomationMutationKills:
    """Mata mutantes 160-169: user key, continue vs break, trigger_count, result keys."""

    def test_trigger_multiple_rules_all_executed(self, user, task):
        """Múltiples reglas habilitadas se ejecutan todas (continue, no break)."""
        AutomationRule.objects.create(
            owner=user, name="R1", trigger=AutomationRule.Trigger.TASK_CREATED,
            action=AutomationRule.Action.SET_PRIORITY,
            action_params={"priority": 1}, enabled=True,
        )
        AutomationRule.objects.create(
            owner=user, name="R2", trigger=AutomationRule.Trigger.TASK_CREATED,
            action=AutomationRule.Action.SET_STATE,
            action_params={"state": "in_progress"}, enabled=True,
        )
        results = trigger_automation(
            AutomationRule.Trigger.TASK_CREATED,
            {"task": task, "user": user},
        )
        assert len(results) == 2  # Si break, sería 1
        rule_names = {r["rule"] for r in results}  # No "XXruleXX"
        assert rule_names == {"R1", "R2"}
        assert all("result" in r for r in results)  # No "XXresultXX"

    def test_trigger_count_increments(self, user, task):
        """trigger_count se incrementa con += 1 (no = 1)."""
        rule = AutomationRule.objects.create(
            owner=user, name="Count", trigger=AutomationRule.Trigger.TASK_CREATED,
            action=AutomationRule.Action.SET_PRIORITY,
            action_params={"priority": 1}, enabled=True,
        )
        # Primera ejecución
        trigger_automation(AutomationRule.Trigger.TASK_CREATED, {"task": task, "user": user})
        rule.refresh_from_db()
        assert rule.trigger_count == 1
        # Segunda ejecución
        trigger_automation(AutomationRule.Trigger.TASK_CREATED, {"task": task, "user": user})
        rule.refresh_from_db()
        assert rule.trigger_count == 2  # Si = 1, seguiría siendo 1

    def test_trigger_user_from_task_sets_context(self, user, task):
        """trigger_automation sin user obtiene de task.owner y lo guarda en context."""
        AutomationRule.objects.create(
            owner=user, name="Auto", trigger=AutomationRule.Trigger.TASK_CREATED,
            action=AutomationRule.Action.SET_PRIORITY,
            action_params={"priority": 2}, enabled=True,
        )
        results = trigger_automation(AutomationRule.Trigger.TASK_CREATED, {"task": task})
        assert len(results) == 1
        # El log debe tener trigger_data con "user" key
        log = AutomationLog.objects.first()
        assert "user" in log.trigger_data  # No "XXuserXX"


# ============================================================================
# automations/engine.py — matar mutantes 263-284 (run_daily_checks)
# ============================================================================

@pytest.mark.django_db(transaction=True)
class TestRunDailyChecksMutationKills:
    """Mata mutantes 263-284: daily check context keys, overdue states, sprint days."""

    def test_daily_check_context_keys(self, user):
        """DAILY_CHECK pasa 'user' y 'check_time' en context."""
        AutomationRule.objects.create(
            owner=user, name="Daily", trigger=AutomationRule.Trigger.DAILY_CHECK,
            action=AutomationRule.Action.CREATE_NOTIFICATION,
            action_params={"title": "Daily check"}, enabled=True,
        )
        run_daily_checks()
        log = AutomationLog.objects.filter(
            rule__trigger=AutomationRule.Trigger.DAILY_CHECK
        ).first()
        assert log is not None
        assert "user" in log.trigger_data  # No "XXuserXX"
        assert "check_time" in log.trigger_data  # No "XXcheck_timeXX"

    def test_daily_check_overdue_context_keys(self, user, task):
        """TASK_OVERDUE pasa 'task', 'user', 'due_date' en context."""
        task.due_date = timezone.now() - timedelta(days=1)
        task.state = "pending"
        task.save()
        AutomationRule.objects.create(
            owner=user, name="Overdue", trigger=AutomationRule.Trigger.TASK_OVERDUE,
            action=AutomationRule.Action.CREATE_NOTIFICATION,
            action_params={"title": "Overdue!"}, enabled=True,
        )
        run_daily_checks()
        log = AutomationLog.objects.filter(
            rule__trigger=AutomationRule.Trigger.TASK_OVERDUE
        ).first()
        assert log is not None
        assert "task" in log.trigger_data  # No "XXtaskXX"
        assert "user" in log.trigger_data  # No "XXuserXX"
        assert "due_date" in log.trigger_data  # No "XXdue_dateXX"

    def test_daily_check_overdue_in_progress_state(self, user, task):
        """Tareas vencidas en estado 'in_progress' también disparan TASK_OVERDUE."""
        task.due_date = timezone.now() - timedelta(days=1)
        task.state = "in_progress"
        task.save()
        AutomationRule.objects.create(
            owner=user, name="Overdue", trigger=AutomationRule.Trigger.TASK_OVERDUE,
            action=AutomationRule.Action.CREATE_NOTIFICATION,
            action_params={"title": "Overdue!"}, enabled=True,
        )
        run_daily_checks()
        assert AutomationLog.objects.filter(
            rule__trigger=AutomationRule.Trigger.TASK_OVERDUE
        ).exists()

    def test_daily_check_overdue_review_state(self, user, task):
        """Tareas vencidas en estado 'review' también disparan TASK_OVERDUE."""
        task.due_date = timezone.now() - timedelta(days=1)
        task.state = "review"
        task.save()
        AutomationRule.objects.create(
            owner=user, name="Overdue", trigger=AutomationRule.Trigger.TASK_OVERDUE,
            action=AutomationRule.Action.CREATE_NOTIFICATION,
            action_params={"title": "Overdue!"}, enabled=True,
        )
        run_daily_checks()
        assert AutomationLog.objects.filter(
            rule__trigger=AutomationRule.Trigger.TASK_OVERDUE
        ).exists()

    def test_daily_check_overdue_blocked_state(self, user, task):
        """Tareas vencidas en estado 'blocked' también disparan TASK_OVERDUE."""
        task.due_date = timezone.now() - timedelta(days=1)
        task.state = "blocked"
        task.save()
        AutomationRule.objects.create(
            owner=user, name="Overdue", trigger=AutomationRule.Trigger.TASK_OVERDUE,
            action=AutomationRule.Action.CREATE_NOTIFICATION,
            action_params={"title": "Overdue!"}, enabled=True,
        )
        run_daily_checks()
        assert AutomationLog.objects.filter(
            rule__trigger=AutomationRule.Trigger.TASK_OVERDUE
        ).exists()

    def test_daily_check_completed_not_overdue(self, user, task):
        """Tareas vencidas en estado 'completed' NO disparan TASK_OVERDUE."""
        task.due_date = timezone.now() - timedelta(days=1)
        task.state = "completed"
        task.save()
        AutomationRule.objects.create(
            owner=user, name="Overdue", trigger=AutomationRule.Trigger.TASK_OVERDUE,
            action=AutomationRule.Action.CREATE_NOTIFICATION,
            action_params={"title": "Overdue!"}, enabled=True,
        )
        run_daily_checks()
        assert not AutomationLog.objects.filter(
            rule__trigger=AutomationRule.Trigger.TASK_OVERDUE
        ).exists()

    def test_daily_check_sprint_ending_2_days(self, user, project):
        """Sprint con end_date dentro de 2 días dispara SPRINT_CLOSED."""
        Sprint.objects.create(
            owner=user, project=project, name="Ending",
            state=Sprint.SprintState.ACTIVE,
            start_date=timezone.now().date() - timedelta(days=10),
            end_date=timezone.now().date() + timedelta(days=2),  # Exactamente 2 días
        )
        AutomationRule.objects.create(
            owner=user, name="SprintEnd", trigger=AutomationRule.Trigger.SPRINT_CLOSED,
            action=AutomationRule.Action.CREATE_NOTIFICATION,
            action_params={"title": "Ending!"}, enabled=True,
        )
        run_daily_checks()
        assert AutomationLog.objects.filter(
            rule__trigger=AutomationRule.Trigger.SPRINT_CLOSED
        ).exists()

    def test_daily_check_sprint_3_days_not_triggered(self, user, project):
        """Sprint con end_date a 3 días NO dispara (mata days=3)."""
        Sprint.objects.create(
            owner=user, project=project, name="Far",
            state=Sprint.SprintState.ACTIVE,
            start_date=timezone.now().date() - timedelta(days=10),
            end_date=timezone.now().date() + timedelta(days=3),  # 3 días, fuera de rango
        )
        AutomationRule.objects.create(
            owner=user, name="SprintFar", trigger=AutomationRule.Trigger.SPRINT_CLOSED,
            action=AutomationRule.Action.CREATE_NOTIFICATION,
            action_params={"title": "Far!"}, enabled=True,
        )
        run_daily_checks()
        assert not AutomationLog.objects.filter(
            rule__name="SprintFar"
        ).exists()


# ============================================================================
# offline_sync/services.py — matar mutantes 171, 190 (register_device, device_id)
# ============================================================================

@pytest.mark.django_db
class TestRegisterDeviceMutationKills:
    """Mata mutante 171: device_name default."""

    def test_register_device_default_empty_name(self, user):
        """register_device sin device_name usa '' como default."""
        dev = register_device(user, "dev-no-name")
        assert dev.device_name == ""  # No "XXXX"


@pytest.mark.django_db(transaction=True)
class TestApplySyncDeviceIdMutationKills:
    """Mata mutante 190: device_id default. device FK es NOT NULL, no se puede matar directamente."""

    def test_apply_operation_with_valid_device_id(self, user, sync_device):
        """Operación con device_id válido linkea correctamente."""
        ops = [{
            "device_id": "dev-test",
            "op_type": "create",
            "entity_type": "task",
            "entity_id": "x",
            "payload": {"title": "With device"},
            "client_timestamp": timezone.now().isoformat(),
        }]
        results = apply_sync_operations(user, ops)
        assert results[0]["status"] == "applied"
        op = SyncOperation.objects.get(entity_id="x")
        assert op.device == sync_device


# ============================================================================
# offline_sync/services.py — matar mutantes 196-242 (response keys, conflict)
# ============================================================================

@pytest.mark.django_db(transaction=True)
class TestTaskSyncResponseKeysMutationKills:
    """Mata mutantes 196-242: response keys exactas."""

    def test_create_task_response_keys(self, user, sync_device):
        """Create task devuelve entity_id, server_id, status."""
        ops = [{
            "device_id": "dev-test",
            "op_type": "create",
            "entity_type": "task",
            "entity_id": "ent1",
            "payload": {"title": "New Task"},
            "client_timestamp": timezone.now().isoformat(),
        }]
        results = apply_sync_operations(user, ops)
        assert results[0]["entity_id"] == "ent1"  # No "XXentity_idXX"
        assert results[0]["server_id"] is not None  # No "XXserver_idXX"
        assert results[0]["status"] == "applied"
        # Verifica server_entity_id en SyncOperation
        op = SyncOperation.objects.get(entity_id="ent1")
        assert op.server_entity_id is not None  # No None
        assert op.applied_at is not None  # No None

    def test_update_task_response_keys(self, user, task, sync_device):
        """Update task devuelve entity_id, server_id, status, current_version."""
        ops = [{
            "device_id": "dev-test",
            "op_type": "update",
            "entity_type": "task",
            "entity_id": "ent2",
            "payload": {"id": task.id, "title": "Updated"},
            "base_version": task.version,
            "client_timestamp": timezone.now().isoformat(),
        }]
        results = apply_sync_operations(user, ops)
        assert results[0]["entity_id"] == "ent2"
        assert results[0]["server_id"] == task.id
        assert results[0]["status"] == "applied"
        assert results[0]["current_version"] is not None  # No "XXcurrent_versionXX"
        op = SyncOperation.objects.get(entity_id="ent2")
        assert op.server_entity_id is not None
        assert op.applied_at is not None

    def test_delete_task_response_keys(self, user, sync_device):
        """Delete task devuelve entity_id y status."""
        task = Task.objects.create(owner=user, title="ToDelete")
        ops = [{
            "device_id": "dev-test",
            "op_type": "delete",
            "entity_type": "task",
            "entity_id": "ent3",
            "payload": {"id": task.id},
            "base_version": task.version,
            "client_timestamp": timezone.now().isoformat(),
        }]
        results = apply_sync_operations(user, ops)
        assert results[0]["entity_id"] == "ent3"  # No "XXentity_idXX"
        assert results[0]["status"] == "applied"
        op = SyncOperation.objects.get(entity_id="ent3")
        assert op.applied_at is not None  # No None

    def test_update_conflict_response_keys(self, user, task, sync_device):
        """Update conflict devuelve entity_id, conflict, current_version, client_version, server_data, status."""
        Task.objects.filter(id=task.id).update(version=5)
        task.refresh_from_db()
        ops = [{
            "device_id": "dev-test",
            "op_type": "update",
            "entity_type": "task",
            "entity_id": "ent4",
            "payload": {"id": task.id, "title": "Conflict"},
            "base_version": 3,
            "client_timestamp": timezone.now().isoformat(),
        }]
        results = apply_sync_operations(user, ops)
        assert results[0]["entity_id"] == "ent4"  # No "XXentity_idXX"
        assert results[0]["conflict"] is True
        assert results[0]["current_version"] == 5
        assert results[0]["client_version"] == 3
        assert results[0]["status"] == "conflict"
        assert "server_data" in results[0]
        # conflict_data no debe ser None
        op = SyncOperation.objects.get(entity_id="ent4")
        assert op.conflict_data is not None  # No None

    def test_delete_conflict_boundary_equal_version(self, user, task, sync_device):
        """Delete con base_version == task.version NO es conflicto (usa <, no <=)."""
        Task.objects.filter(id=task.id).update(version=5)
        task.refresh_from_db()
        ops = [{
            "device_id": "dev-test",
            "op_type": "delete",
            "entity_type": "task",
            "entity_id": "ent5",
            "payload": {"id": task.id},
            "base_version": 5,  # Igual a task.version → NO conflicto
            "client_timestamp": timezone.now().isoformat(),
        }]
        results = apply_sync_operations(user, ops)
        # Si usa <=, sería conflict. Si usa <, es applied.
        assert results[0]["status"] == "applied"  # No "conflict"


@pytest.fixture
def sync_device(user):
    return SyncDevice.objects.create(user=user, device_id="dev-test", device_name="Test")


# ============================================================================
# offline_sync/services.py — matar mutantes 246-261 (_filter_task_fields, _task_to_dict)
# ============================================================================

class TestFilterTaskFieldsMutationKills:
    """Mata mutantes 246-251: cada campo de allowed."""

    def test_filter_all_fields_preserved(self):
        """Todos los campos allowed se preservan."""
        payload = {
            "title": "T", "description": "D", "state": "pending",
            "priority": 3, "due_date": "2024-01-01", "start_date": "2024-01-01",
            "story_points": 5,
        }
        result = _filter_task_fields(payload)
        assert "title" in result  # No "XXtitleXX"
        assert "description" in result  # No "XXdescriptionXX"
        assert "state" in result  # No "XXstateXX"
        assert "priority" in result  # No "XXpriorityXX"
        assert "due_date" in result  # No "XXdue_dateXX"
        assert "start_date" in result  # No "XXstart_dateXX"
        assert "story_points" in result  # No "XXstory_pointsXX"
        assert result["title"] == "T"
        assert result["description"] == "D"
        assert result["state"] == "pending"
        assert result["priority"] == 3
        assert result["due_date"] == "2024-01-01"
        assert result["start_date"] == "2024-01-01"
        assert result["story_points"] == 5

    def test_filter_excludes_non_allowed(self):
        """Campos no allowed se excluyen."""
        payload = {"title": "T", "id": 1, "owner_id": 2, "version": 3}
        result = _filter_task_fields(payload)
        assert "title" in result
        assert "id" not in result
        assert "owner_id" not in result
        assert "version" not in result


@pytest.mark.django_db
class TestTaskToDictMutationKills:
    """Mata mutantes 255-261: _task_to_dict keys exactas."""

    def test_task_to_dict_keys(self, user, task):
        """_task_to_dict devuelve todas las keys correctas."""
        d = _task_to_dict(task)
        assert "id" in d
        assert "title" in d  # No "XXtitleXX"
        assert "description" in d  # No "XXdescriptionXX"
        assert "state" in d  # No "XXstateXX"
        assert "priority" in d  # No "XXpriorityXX"
        assert "due_date" in d  # No "XXdue_dateXX"
        assert "updated_at" in d  # No "XXupdated_atXX"
        assert "version" in d  # No "XXversionXX"
        assert d["id"] == task.id
        assert d["title"] == task.title
        assert d["description"] == task.description
        assert d["state"] == task.state
        assert d["priority"] == task.priority


# ============================================================================
# offline_sync/services.py — matar mutantes 266-271 (export projects)
# ============================================================================

@pytest.mark.django_db
class TestGetChangesSinceProjectKeysMutationKills:
    """Mata mutantes 266-271: project dict keys en get_changes_since."""

    def test_project_export_keys(self, user, project):
        """get_changes_since exporta projects con keys exactas."""
        project.save()  # Actualizar updated_at
        changes = get_changes_since(user, timezone.now() - timedelta(days=1))
        assert len(changes["projects"]) >= 1
        p = changes["projects"][0]
        assert "id" in p  # No "XXidXX"
        assert "name" in p  # No "XXnameXX"
        assert "description" in p  # No "XXdescriptionXX"
        assert "color" in p  # No "XXcolorXX"
        assert "is_archived" in p  # No "XXis_archivedXX"
        assert "updated_at" in p  # No "XXupdated_atXX"
        assert p["id"] == project.id
        assert p["name"] == project.name
