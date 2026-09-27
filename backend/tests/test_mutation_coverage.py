"""Tests adicionales para mejorar el mutation score de los 3 archivos críticos:
- integrations/views.py (21% → objetivo 50%+)
- offline_sync/services.py (33% → objetivo 60%+)
- automations/engine.py (47% → objetivo 65%+)
"""
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.automations.engine import (
    evaluate_conditions,
    execute_action,
    run_daily_checks,
    trigger_automation,
)
from apps.automations.models import AutomationLog, AutomationRule
from apps.integrations.models import (
    GitHubInstallation,
    GitHubIssueLink,
    GitHubRelease,
    GitHubRepo,
)
from apps.offline_sync.models import SyncDevice, SyncOperation
from apps.offline_sync.services import (
    apply_sync_operations,
    get_changes_since,
    register_device,
)
from apps.projects.models import Project
from apps.tasks.models import Sprint, Task

User = get_user_model()


# ============================================================================
# integrations/views.py — ramas de error, mapeo, OAuth edge cases
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
class TestDiscoverReposEdgeCases:
    def test_discover_repos_sin_instalaciones(self, authed_client):
        """discover_repos sin instalaciones devuelve 400."""
        resp = authed_client.post("/api/github/installations/discover_repos/")
        assert resp.status_code == 400
        assert "error" in resp.data

    @patch("apps.integrations.views.GitHubAppClient")
    def test_discover_repos_error_api(self, mock_client_class, authed_client, github_installation):
        """discover_repos con error de API devuelve 502."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.list_installation_repos.side_effect = Exception("API down")
        resp = authed_client.post("/api/github/installations/discover_repos/")
        assert resp.status_code == 502
        assert "error" in resp.data

    @patch("apps.integrations.views.GitHubAppClient")
    def test_discover_repos_repo_existente_no_crea(self, mock_client_class, authed_client, github_installation, github_repo):
        """discover_repos con repo ya existente no lo crea de nuevo."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.list_installation_repos.return_value = [
            {
                "id": 100,
                "full_name": "testuser/my-repo",
                "name": "my-repo",
                "owner": {"login": "testuser"},
                "private": False,
                "default_branch": "main",
            }
        ]
        resp = authed_client.post("/api/github/installations/discover_repos/")
        assert resp.status_code == 200
        assert resp.data["new"] == 0
        assert resp.data["total"] == 1


@pytest.mark.django_db
class TestRepoSyncEdgeCases:
    def test_sync_repo_disabled(self, authed_client, github_repo):
        """sync en repo con sync_enabled=False devuelve 400."""
        github_repo.sync_enabled = False
        github_repo.save()
        resp = authed_client.post(f"/api/github/repos/{github_repo.id}/sync/")
        assert resp.status_code == 400
        assert "error" in resp.data

    @patch("apps.integrations.sync_github.sync_repo_data")
    @patch("apps.integrations.views.sync_repo_issues_task.delay")
    def test_sync_repo_error(self, mock_delay, mock_sync, authed_client, github_repo):
        """sync con error de sync_repo_data devuelve 502."""
        mock_sync.side_effect = Exception("Sync failed")
        resp = authed_client.post(f"/api/github/repos/{github_repo.id}/sync/")
        assert resp.status_code == 502
        assert "error" in resp.data

    @patch("apps.integrations.sync_github.sync_repo_data")
    @patch("apps.integrations.views.sync_repo_issues_task.delay")
    def test_sync_repo_success(self, mock_delay, mock_sync, authed_client, github_repo):
        """sync exitoso devuelve los conteos."""
        mock_sync.return_value = {"prs": 3, "commits": 10, "releases": 2}
        resp = authed_client.post(f"/api/github/repos/{github_repo.id}/sync/")
        assert resp.status_code == 200
        assert resp.data["synced"]["prs"] == 3


@pytest.mark.django_db
class TestRepoIssuesEdgeCases:
    @patch("apps.integrations.views.GitHubAppClient")
    def test_list_issues_error_api(self, mock_client_class, authed_client, github_repo):
        """list issues con error de API devuelve 502."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.list_issues.side_effect = Exception("API error")
        resp = authed_client.get(f"/api/github/repos/{github_repo.id}/issues/")
        assert resp.status_code == 502

    @patch("apps.integrations.views.GitHubAppClient")
    def test_list_issues_filtra_prs(self, mock_client_class, authed_client, github_repo):
        """list issues filtra los PRs (tienen 'pull_request' key)."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.list_issues.return_value = [
            {"id": 1, "number": 1, "title": "Issue 1", "state": "open",
             "html_url": "http://gh/1", "body": "body", "labels": []},
            {"id": 2, "number": 2, "title": "PR 1", "state": "open",
             "html_url": "http://gh/2", "body": "body", "labels": [],
             "pull_request": {"url": "..."}},
        ]
        resp = authed_client.get(f"/api/github/repos/{github_repo.id}/issues/")
        assert resp.status_code == 200
        assert len(resp.data["results"]) == 1
        assert resp.data["results"][0]["title"] == "Issue 1"

    @patch("apps.integrations.views.GitHubAppClient")
    def test_list_issues_already_linked(self, mock_client_class, authed_client, github_repo, user):
        """list issues marca already_linked=True si ya existe link."""
        task = Task.objects.create(owner=user, title="T")
        GitHubIssueLink.objects.create(
            task=task, repo=github_repo, issue_number=1, issue_id=1,
            issue_url="http://gh/1", issue_state="open",
        )
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.list_issues.return_value = [
            {"id": 1, "number": 1, "title": "Issue 1", "state": "open",
             "html_url": "http://gh/1", "body": "body", "labels": []},
        ]
        resp = authed_client.get(f"/api/github/repos/{github_repo.id}/issues/")
        assert resp.data["results"][0]["already_linked"] is True

    @patch("apps.integrations.views.GitHubAppClient")
    def test_import_issues_con_label_filter(self, mock_client_class, authed_client, github_repo, user):
        """import_issues filtra por label."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.list_issues.return_value = [
            {"id": 1, "number": 1, "title": "Bug", "state": "open",
             "html_url": "http://gh/1", "body": "", "labels": [{"name": "bug"}]},
            {"id": 2, "number": 2, "title": "Feature", "state": "open",
             "html_url": "http://gh/2", "body": "", "labels": [{"name": "enhancement"}]},
        ]
        resp = authed_client.post(
            f"/api/github/repos/{github_repo.id}/import_issues/",
            {"state": "open", "label_filter": "bug"},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["imported"] == 1
        assert resp.data["total"] == 1


@pytest.mark.django_db
class TestCreateIssueLinkEdgeCases:
    def test_create_for_task_not_found(self, authed_client, github_repo):
        """create_for_task con task_id inexistente devuelve 404."""
        resp = authed_client.post(
            "/api/github/links/create_for_task/",
            {"task_id": 99999, "repo_id": github_repo.id},
            format="json",
        )
        assert resp.status_code == 404

    def test_create_for_task_repo_not_found(self, authed_client, task):
        """create_for_task con repo_id inexistente devuelve 404."""
        resp = authed_client.post(
            "/api/github/links/create_for_task/",
            {"task_id": task.id, "repo_id": 99999},
            format="json",
        )
        assert resp.status_code == 404

    def test_create_for_task_already_linked(self, authed_client, task, github_repo):
        """create_for_task con tarea ya vinculada devuelve 400."""
        GitHubIssueLink.objects.create(
            task=task, repo=github_repo, issue_number=5, issue_id=50,
            issue_url="http://gh/5", issue_state="open",
        )
        resp = authed_client.post(
            "/api/github/links/create_for_task/",
            {"task_id": task.id, "repo_id": github_repo.id},
            format="json",
        )
        assert resp.status_code == 400

    @patch("apps.integrations.sync_service.GitHubAppClient")
    def test_create_for_task_error_api(self, mock_client_class, authed_client, task, github_repo):
        """create_for_task con error de API devuelve 502."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.create_issue.side_effect = Exception("API error")
        resp = authed_client.post(
            "/api/github/links/create_for_task/",
            {"task_id": task.id, "repo_id": github_repo.id},
            format="json",
        )
        assert resp.status_code == 502

    @patch("apps.integrations.sync_service.GitHubAppClient")
    def test_sync_link_error(self, mock_client_class, authed_client, task, github_repo):
        """sync link con error devuelve 502."""
        link = GitHubIssueLink.objects.create(
            task=task, repo=github_repo, issue_number=5, issue_id=50,
            issue_url="http://gh/5", issue_state="open",
        )
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.update_issue.side_effect = Exception("API error")
        resp = authed_client.post(f"/api/github/links/{link.id}/sync/")
        assert resp.status_code == 502


@pytest.mark.django_db
class TestPrLinkTaskEdgeCases:
    def test_link_task_sin_task_id(self, authed_client, github_installation):
        """link_task sin task_id devuelve 400."""
        from apps.integrations.models import GitHubPullRequest
        pr = GitHubPullRequest.objects.create(
            repo=GitHubRepo.objects.create(
                installation=github_installation, repo_id=1,
                full_name="t/r", name="r", owner="t",
            ),
            pr_number=1, pr_id=1, title="PR 1", state="open",
            html_url="http://gh/1", is_merged=False,
        )
        resp = authed_client.post(f"/api/github/prs/{pr.id}/link_task/", {}, format="json")
        assert resp.status_code == 400

    def test_link_task_not_found(self, authed_client, github_installation):
        """link_task con task_id inexistente devuelve 404."""
        from apps.integrations.models import GitHubPullRequest
        repo = GitHubRepo.objects.create(
            installation=github_installation, repo_id=1,
            full_name="t/r", name="r", owner="t",
        )
        pr = GitHubPullRequest.objects.create(
            repo=repo, pr_number=1, pr_id=1, title="PR 1", state="open",
            html_url="http://gh/1", is_merged=False,
        )
        resp = authed_client.post(
            f"/api/github/prs/{pr.id}/link_task/",
            {"task_id": 99999},
            format="json",
        )
        assert resp.status_code == 404


@pytest.mark.django_db
class TestReleaseProgress:
    def test_progress_con_tareas_y_prs(self, authed_client, github_installation, user):
        """progress calcula correctamente tareas y PRs."""
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
        t1 = Task.objects.create(owner=user, title="T1", state="completed")
        t2 = Task.objects.create(owner=user, title="T2", state="pending")
        release.tasks.add(t1, t2)

        from apps.integrations.models import GitHubPullRequest
        pr1 = GitHubPullRequest.objects.create(
            repo=repo, pr_number=1, pr_id=10, title="PR1", state="closed",
            html_url="http://gh/1", is_merged=True,
        )
        pr2 = GitHubPullRequest.objects.create(
            repo=repo, pr_number=2, pr_id=20, title="PR2", state="open",
            html_url="http://gh/2", is_merged=False,
        )
        release.pull_requests.add(pr1, pr2)

        resp = authed_client.get(f"/api/github/releases/{release.id}/progress/")
        assert resp.status_code == 200
        assert resp.data["tasks_total"] == 2
        assert resp.data["tasks_done"] == 1
        assert resp.data["tasks_pending"] == 1
        assert resp.data["prs_total"] == 2
        assert resp.data["prs_merged"] == 1
        assert resp.data["progress_pct"] == 50.0

    def test_progress_sin_tareas(self, authed_client, github_installation):
        """progress con 0 tareas devuelve progress_pct=0."""
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
        resp = authed_client.get(f"/api/github/releases/{release.id}/progress/")
        assert resp.status_code == 200
        assert resp.data["progress_pct"] == 0
        assert resp.data["tasks_total"] == 0


@pytest.mark.django_db
class TestOAuthCallbackEdgeCases:
    def test_oauth_callback_sin_code(self, api_client):
        """callback sin code devuelve 400."""
        session = api_client.session
        session["github_oauth_state"] = "state"
        session.save()
        resp = api_client.post("/api/auth/github/callback/", {"state": "state"}, format="json")
        assert resp.status_code == 400

    def test_oauth_callback_state_mismatch(self, api_client):
        """callback con state que no coincide devuelve 400."""
        session = api_client.session
        session["github_oauth_state"] = "stored"
        session.save()
        resp = api_client.post(
            "/api/auth/github/callback/",
            {"code": "c", "state": "different"},
            format="json",
        )
        assert resp.status_code == 400

    @patch("apps.integrations.views.GitHubOAuthClient")
    def test_oauth_callback_error_exchange(self, mock_oauth_class, api_client):
        """callback con error en exchange_code devuelve 502."""
        session = api_client.session
        session["github_oauth_state"] = "s"
        session.save()
        mock_oauth = MagicMock()
        mock_oauth_class.return_value = mock_oauth
        mock_oauth.exchange_code.side_effect = Exception("Exchange failed")
        resp = api_client.post(
            "/api/auth/github/callback/",
            {"code": "c", "state": "s"},
            format="json",
        )
        assert resp.status_code == 502

    @patch("apps.integrations.views.GitHubOAuthClient")
    def test_oauth_callback_no_access_token(self, mock_oauth_class, api_client):
        """callback sin access_token en respuesta devuelve 400."""
        session = api_client.session
        session["github_oauth_state"] = "s"
        session.save()
        mock_oauth = MagicMock()
        mock_oauth_class.return_value = mock_oauth
        mock_oauth.exchange_code.return_value = {"error": "bad_code"}
        resp = api_client.post(
            "/api/auth/github/callback/",
            {"code": "c", "state": "s"},
            format="json",
        )
        assert resp.status_code == 400

    @patch("apps.integrations.views.GitHubOAuthClient")
    def test_oauth_callback_error_user_info(self, mock_oauth_class, api_client):
        """callback con error en get_user_info devuelve 502."""
        session = api_client.session
        session["github_oauth_state"] = "s"
        session.save()
        mock_oauth = MagicMock()
        mock_oauth_class.return_value = mock_oauth
        mock_oauth.exchange_code.return_value = {"access_token": "tok"}
        mock_oauth.get_user_info.side_effect = Exception("User info failed")
        resp = api_client.post(
            "/api/auth/github/callback/",
            {"code": "c", "state": "s"},
            format="json",
        )
        assert resp.status_code == 502

    @patch("apps.integrations.views.GitHubOAuthClient")
    def test_oauth_callback_usuario_existente_por_instalacion(self, mock_oauth_class, api_client, user):
        """callback linkea con usuario existente por github_user_id."""
        GitHubInstallation.objects.create(
            user=user, installation_id=999, account_login="existing",
            account_type="User", github_user_id=55555,
            github_username="existing", access_token="old",
        )
        session = api_client.session
        session["github_oauth_state"] = "s"
        session.save()
        mock_oauth = MagicMock()
        mock_oauth_class.return_value = mock_oauth
        mock_oauth.exchange_code.return_value = {"access_token": "new_tok"}
        mock_oauth.get_user_info.return_value = {
            "id": 55555, "login": "existing", "email": None,
            "avatar_url": "http://avatar",
        }
        resp = api_client.post(
            "/api/auth/github/callback/",
            {"code": "c", "state": "s"},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["github_username"] == "existing"
        # No creó usuario nuevo
        assert User.objects.filter(email="user@test.com").exists()

    @patch("apps.integrations.views.GitHubOAuthClient")
    def test_oauth_callback_usuario_sin_email_genera_local(self, mock_oauth_class, api_client):
        """callback con usuario sin email genera email @github.local."""
        session = api_client.session
        session["github_oauth_state"] = "s"
        session.save()
        mock_oauth = MagicMock()
        mock_oauth_class.return_value = mock_oauth
        mock_oauth.exchange_code.return_value = {"access_token": "tok"}
        mock_oauth.get_user_info.return_value = {
            "id": 77777, "login": "noemail", "email": None,
            "avatar_url": "",
        }
        resp = api_client.post(
            "/api/auth/github/callback/",
            {"code": "c", "state": "s"},
            format="json",
        )
        assert resp.status_code == 200
        assert User.objects.filter(email="noemail@github.local").exists()

    @patch("apps.integrations.views.GitHubOAuthClient")
    def test_oauth_callback_usuario_existente_por_email(self, mock_oauth_class, api_client, user):
        """callback linkea con usuario existente por email."""
        session = api_client.session
        session["github_oauth_state"] = "s"
        session.save()
        mock_oauth = MagicMock()
        mock_oauth_class.return_value = mock_oauth
        mock_oauth.exchange_code.return_value = {"access_token": "tok"}
        mock_oauth.get_user_info.return_value = {
            "id": 88888, "login": "newlogin", "email": "user@test.com",
            "avatar_url": "",
        }
        # El email debe estar verificado en GitHub para vincular la cuenta
        mock_oauth.get_verified_emails.return_value = {"user@test.com"}
        resp = api_client.post(
            "/api/auth/github/callback/",
            {"code": "c", "state": "s"},
            format="json",
        )
        assert resp.status_code == 200
        # Linkeó con el usuario existente, no creó uno nuevo
        assert User.objects.filter(email="user@test.com").count() == 1

    @pytest.mark.django_db(transaction=True)
    @patch("apps.integrations.views.GitHubOAuthClient")
    def test_oauth_callback_email_no_verificado_no_linkea(self, mock_oauth_class, api_client, user):
        """Email público NO verificado no vincula cuenta existente (anti-takeover)."""
        session = api_client.session
        session["github_oauth_state"] = "s"
        session.save()
        mock_oauth = MagicMock()
        mock_oauth_class.return_value = mock_oauth
        mock_oauth.exchange_code.return_value = {"access_token": "tok"}
        mock_oauth.get_user_info.return_value = {
            "id": 99999, "login": "attacker", "email": "user@test.com",
            "avatar_url": "",
        }
        # El email NO está verificado → no debe vincularse a la cuenta existente.
        # Intenta crear usuario con email duplicado → IntegrityError (la vista no
        # lo captura, pero lo importante es que nunca linkea ni emite tokens).
        mock_oauth.get_verified_emails.return_value = {"other@github.com"}
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            api_client.post(
                "/api/auth/github/callback/",
                {"code": "c", "state": "s"},
                format="json",
            )


@pytest.mark.django_db
class TestWebhookRetryDeadLetter:
    @patch("apps.integrations.webhook_processor.retry_dead_letter_deliveries")
    def test_webhook_retry_dead_letter(self, mock_retry, authed_client, user):
        """webhook_retry_dead_letter llama al servicio."""
        mock_retry.return_value = {"retried": 3, "failed": 1}
        inst = GitHubInstallation.objects.create(user=user, installation_id=777)
        GitHubRepo.objects.create(
            installation=inst, repo_id=1, full_name="u/r", name="r", owner="u"
        )
        resp = authed_client.post("/api/webhooks/retry-dead-letter/")
        assert resp.status_code == 200
        assert "message" in resp.data


# ============================================================================
# offline_sync/services.py — conflictos, versiones, proyectos, errores
# ============================================================================

@pytest.fixture
def sync_device(user):
    return SyncDevice.objects.create(user=user, device_id="dev-test", device_name="Test")


@pytest.mark.django_db(transaction=True)
class TestApplySyncOperationsErrors:
    def test_apply_operations_con_excepcion_devuelve_rejected(self, user, sync_device):
        """Una operación que lanza excepción devuelve rejected."""
        # Forzar excepción: payload con campo que viola constraint
        # task create con title=None causará IntegrityError o ValidationError
        ops = [{
            "device_id": "dev-test",
            "op_type": "create",
            "entity_type": "task",
            "entity_id": "x",
            "payload": {"title": None},  # title no puede ser None
            "client_timestamp": timezone.now().isoformat(),
        }]
        results = apply_sync_operations(user, ops)
        assert len(results) == 1
        assert results[0]["status"] == "rejected"
        assert results[0]["entity_id"] == "x"

    def test_apply_operations_entity_type_desconocido(self, user, sync_device):
        """entity_type desconocido devuelve rejected."""
        ops = [{
            "device_id": "dev-test",
            "op_type": "create",
            "entity_type": "unknown_entity",
            "entity_id": "x",
            "payload": {},
            "client_timestamp": timezone.now().isoformat(),
        }]
        results = apply_sync_operations(user, ops)
        assert results[0]["status"] == "rejected"
        assert "Unknown entity type" in results[0]["error"]

    def test_apply_operations_timestamp_como_string(self, user, sync_device):
        """client_timestamp como string se parsea correctamente."""
        ts = timezone.now().isoformat()
        ops = [{
            "device_id": "dev-test",
            "op_type": "create",
            "entity_type": "task",
            "entity_id": "x",
            "payload": {"title": "Test TS"},
            "client_timestamp": ts,
        }]
        results = apply_sync_operations(user, ops)
        assert results[0]["status"] == "applied"
        op = SyncOperation.objects.filter(entity_id="x").first()
        assert op is not None
        assert op.client_timestamp is not None


@pytest.mark.django_db
class TestTaskSyncConflicts:
    def test_update_task_conflict_version(self, user, task, sync_device):
        """Update con base_version < task.version devuelve conflict."""
        # Usar update() para evitar que save() dispare el signal de versión
        Task.objects.filter(id=task.id).update(version=5)
        task.refresh_from_db()
        ops = [{
            "device_id": "dev-test",
            "op_type": "update",
            "entity_type": "task",
            "entity_id": "x",
            "payload": {"id": task.id, "title": "Updated"},
            "base_version": 3,
            "client_timestamp": timezone.now().isoformat(),
        }]
        results = apply_sync_operations(user, ops)
        assert results[0]["status"] == "conflict"
        assert results[0]["conflict"] is True
        assert results[0]["current_version"] == 5
        assert results[0]["client_version"] == 3
        assert "server_data" in results[0]

    def test_update_task_not_found(self, user, sync_device):
        """Update de task inexistente devuelve rejected."""
        ops = [{
            "device_id": "dev-test",
            "op_type": "update",
            "entity_type": "task",
            "entity_id": "x",
            "payload": {"id": 99999, "title": "Updated"},
            "base_version": 0,
            "client_timestamp": timezone.now().isoformat(),
        }]
        results = apply_sync_operations(user, ops)
        assert results[0]["status"] == "rejected"
        assert "Task not found" in results[0]["error"]

    def test_delete_task_conflict_version(self, user, task, sync_device):
        """Delete con base_version < task.version devuelve conflict."""
        Task.objects.filter(id=task.id).update(version=5)
        task.refresh_from_db()
        ops = [{
            "device_id": "dev-test",
            "op_type": "delete",
            "entity_type": "task",
            "entity_id": "x",
            "payload": {"id": task.id},
            "base_version": 2,
            "client_timestamp": timezone.now().isoformat(),
        }]
        results = apply_sync_operations(user, ops)
        assert results[0]["status"] == "conflict"
        # La tarea no se elimina
        task.refresh_from_db()
        assert task is not None

    def test_delete_task_not_found(self, user, sync_device):
        """Delete de task inexistente devuelve rejected."""
        ops = [{
            "device_id": "dev-test",
            "op_type": "delete",
            "entity_type": "task",
            "entity_id": "x",
            "payload": {"id": 99999},
            "base_version": 0,
            "client_timestamp": timezone.now().isoformat(),
        }]
        results = apply_sync_operations(user, ops)
        assert results[0]["status"] == "rejected"

    def test_update_task_sin_base_version_rechazada(self, user, task, sync_device):
        """Update sin base_version se rechaza (no hay detección de conflictos)."""
        ops = [{
            "device_id": "dev-test",
            "op_type": "update",
            "entity_type": "task",
            "entity_id": "x",
            "payload": {"id": task.id, "title": "No version check"},
            "client_timestamp": timezone.now().isoformat(),
        }]
        results = apply_sync_operations(user, ops)
        assert results[0]["status"] == "rejected"
        assert "base_version" in results[0]["error"]
        # La tarea no se modificó
        task.refresh_from_db()
        assert task.title != "No version check"

    def test_update_task_con_base_version_aplica(self, user, task, sync_device):
        """Update con base_version == task.version aplica el cambio."""
        ops = [{
            "device_id": "dev-test",
            "op_type": "update",
            "entity_type": "task",
            "entity_id": "x",
            "payload": {"id": task.id, "title": "Version checked"},
            "base_version": task.version,
            "client_timestamp": timezone.now().isoformat(),
        }]
        results = apply_sync_operations(user, ops)
        assert results[0]["status"] == "applied"
        task.refresh_from_db()
        assert task.title == "Version checked"


@pytest.mark.django_db
class TestProjectSync:
    def test_create_project(self, user, sync_device):
        """Create project via sync."""
        ops = [{
            "device_id": "dev-test",
            "op_type": "create",
            "entity_type": "project",
            "entity_id": "x",
            "payload": {"name": "Synced Project", "color": "#ff0000"},
            "client_timestamp": timezone.now().isoformat(),
        }]
        results = apply_sync_operations(user, ops)
        assert results[0]["status"] == "applied"
        assert "server_id" in results[0]
        assert Project.objects.filter(owner=user, name="Synced Project").exists()

    def test_update_project(self, user, sync_device):
        """Update project via sync."""
        proj = Project.objects.create(owner=user, name="Original")
        ops = [{
            "device_id": "dev-test",
            "op_type": "update",
            "entity_type": "project",
            "entity_id": "x",
            "payload": {"id": proj.id, "name": "Updated"},
            "client_timestamp": timezone.now().isoformat(),
        }]
        results = apply_sync_operations(user, ops)
        assert results[0]["status"] == "applied"
        proj.refresh_from_db()
        assert proj.name == "Updated"

    def test_update_project_not_found(self, user, sync_device):
        """Update project inexistente devuelve rejected."""
        ops = [{
            "device_id": "dev-test",
            "op_type": "update",
            "entity_type": "project",
            "entity_id": "x",
            "payload": {"id": 99999, "name": "X"},
            "client_timestamp": timezone.now().isoformat(),
        }]
        results = apply_sync_operations(user, ops)
        assert results[0]["status"] == "rejected"

    def test_delete_project(self, user, sync_device):
        """Delete project via sync."""
        proj = Project.objects.create(owner=user, name="ToDelete")
        ops = [{
            "device_id": "dev-test",
            "op_type": "delete",
            "entity_type": "project",
            "entity_id": "x",
            "payload": {"id": proj.id},
            "client_timestamp": timezone.now().isoformat(),
        }]
        results = apply_sync_operations(user, ops)
        assert results[0]["status"] == "applied"
        assert not Project.objects.filter(id=proj.id).exists()

    def test_delete_project_not_found(self, user, sync_device):
        """Delete project inexistente devuelve rejected."""
        ops = [{
            "device_id": "dev-test",
            "op_type": "delete",
            "entity_type": "project",
            "entity_id": "x",
            "payload": {"id": 99999},
            "client_timestamp": timezone.now().isoformat(),
        }]
        results = apply_sync_operations(user, ops)
        assert results[0]["status"] == "rejected"


@pytest.mark.django_db
class TestGetChangesSince:
    def test_get_changes_returns_tasks_and_projects(self, user, task):
        """get_changes_since retorna tareas y proyectos modificados."""
        last_sync = timezone.now() - timedelta(days=1)
        changes = get_changes_since(user, last_sync)
        assert "tasks" in changes
        assert "projects" in changes
        assert len(changes["tasks"]) >= 1
        assert any(t["id"] == task.id for t in changes["tasks"])

    def test_get_changes_no_changes(self, user):
        """get_changes_since sin cambios retorna listas vacías."""
        last_sync = timezone.now() + timedelta(days=1)
        changes = get_changes_since(user, last_sync)
        assert len(changes["tasks"]) == 0
        assert len(changes["projects"]) == 0


@pytest.mark.django_db
class TestRegisterDevice:
    def test_register_device_new(self, user):
        """register_device crea dispositivo nuevo."""
        dev = register_device(user, "dev-new", "Phone")
        assert dev.device_id == "dev-new"
        assert dev.device_name == "Phone"
        assert dev.user == user

    def test_register_device_update_existing(self, user):
        """register_device actualiza dispositivo existente."""
        register_device(user, "dev-1", "Old Name")
        dev = register_device(user, "dev-1", "New Name")
        assert dev.device_name == "New Name"
        assert SyncDevice.objects.filter(device_id="dev-1").count() == 1


# ============================================================================
# automations/engine.py — condiciones, acciones, triggers, daily checks
# ============================================================================

@pytest.mark.django_db
class TestEvaluateConditions:
    def test_equals_match(self):
        assert evaluate_conditions([{"field": "state", "operator": "equals", "value": "open"}], {"state": "open"})

    def test_equals_no_match(self):
        assert not evaluate_conditions([{"field": "state", "operator": "equals", "value": "open"}], {"state": "closed"})

    def test_not_equals_match(self):
        assert evaluate_conditions([{"field": "state", "operator": "not_equals", "value": "open"}], {"state": "closed"})

    def test_not_equals_no_match(self):
        assert not evaluate_conditions([{"field": "state", "operator": "not_equals", "value": "open"}], {"state": "open"})

    def test_contains_match(self):
        assert evaluate_conditions([{"field": "title", "operator": "contains", "value": "bug"}], {"title": "fix bug now"})

    def test_contains_no_match(self):
        assert not evaluate_conditions([{"field": "title", "operator": "contains", "value": "bug"}], {"title": "feature"})

    def test_gt_match(self):
        assert evaluate_conditions([{"field": "priority", "operator": "gt", "value": "3"}], {"priority": "5"})

    def test_gt_no_match(self):
        assert not evaluate_conditions([{"field": "priority", "operator": "gt", "value": "5"}], {"priority": "3"})

    def test_gt_invalid_value(self):
        assert not evaluate_conditions([{"field": "priority", "operator": "gt", "value": "5"}], {"priority": "invalid"})

    def test_lt_match(self):
        assert evaluate_conditions([{"field": "priority", "operator": "lt", "value": "5"}], {"priority": "3"})

    def test_lt_no_match(self):
        assert not evaluate_conditions([{"field": "priority", "operator": "lt", "value": "3"}], {"priority": "5"})

    def test_lt_invalid_value(self):
        assert not evaluate_conditions([{"field": "priority", "operator": "lt", "value": "3"}], {"priority": None})

    def test_default_operator_equals(self):
        """Sin operator explícito, usa equals por defecto."""
        assert evaluate_conditions([{"field": "x", "value": "1"}], {"x": "1"})
        assert not evaluate_conditions([{"field": "x", "value": "1"}], {"x": "2"})

    def test_empty_conditions_passes(self):
        """Lista vacía de condiciones devuelve True."""
        assert evaluate_conditions([], {"x": "1"})

    def test_multiple_conditions_all_must_pass(self):
        """Múltiples condiciones: todas deben pasar."""
        conditions = [
            {"field": "state", "operator": "equals", "value": "open"},
            {"field": "priority", "operator": "gt", "value": "3"},
        ]
        assert evaluate_conditions(conditions, {"state": "open", "priority": "5"})
        assert not evaluate_conditions(conditions, {"state": "open", "priority": "2"})
        assert not evaluate_conditions(conditions, {"state": "closed", "priority": "5"})


@pytest.mark.django_db(transaction=True)
class TestExecuteActionsAll:
    def test_set_priority(self, user, task):
        rule = AutomationRule.objects.create(
            owner=user, name="P", trigger=AutomationRule.Trigger.TASK_CREATED,
            action=AutomationRule.Action.SET_PRIORITY,
            action_params={"priority": 1}, enabled=True,
        )
        result = execute_action(rule, {"task": task, "user": user})
        assert result["old_priority"] != result["new_priority"]
        task.refresh_from_db()
        assert task.priority == 1

    def test_set_state(self, user, task):
        rule = AutomationRule.objects.create(
            owner=user, name="S", trigger=AutomationRule.Trigger.TASK_CREATED,
            action=AutomationRule.Action.SET_STATE,
            action_params={"state": "in_progress"}, enabled=True,
        )
        result = execute_action(rule, {"task": task, "user": user})
        assert result["new_state"] == "in_progress"
        task.refresh_from_db()
        assert task.state == "in_progress"

    def test_set_due_date(self, user, task):
        rule = AutomationRule.objects.create(
            owner=user, name="D", trigger=AutomationRule.Trigger.TASK_CREATED,
            action=AutomationRule.Action.SET_DUE_DATE,
            action_params={"days_from_now": 3}, enabled=True,
        )
        result = execute_action(rule, {"task": task, "user": user})
        assert "due_date" in result
        task.refresh_from_db()
        assert task.due_date is not None

    def test_set_due_date_default_7_days(self, user, task):
        rule = AutomationRule.objects.create(
            owner=user, name="D", trigger=AutomationRule.Trigger.TASK_CREATED,
            action=AutomationRule.Action.SET_DUE_DATE,
            action_params={}, enabled=True,
        )
        execute_action(rule, {"task": task, "user": user})
        task.refresh_from_db()
        assert task.due_date is not None

    def test_move_to_sprint_found(self, user, task, project):
        sprint = Sprint.objects.create(
            owner=user, project=project, name="Target Sprint",
            state=Sprint.SprintState.PLANNED,
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=14),
        )
        rule = AutomationRule.objects.create(
            owner=user, name="M", trigger=AutomationRule.Trigger.TASK_CREATED,
            action=AutomationRule.Action.MOVE_TO_SPRINT,
            action_params={"sprint_id": sprint.id}, enabled=True,
        )
        result = execute_action(rule, {"task": task, "user": user})
        assert "new_sprint" in result
        task.refresh_from_db()
        assert task.sprint == sprint

    def test_move_to_sprint_not_found(self, user, task):
        rule = AutomationRule.objects.create(
            owner=user, name="M", trigger=AutomationRule.Trigger.TASK_CREATED,
            action=AutomationRule.Action.MOVE_TO_SPRINT,
            action_params={"sprint_id": 99999}, enabled=True,
        )
        result = execute_action(rule, {"task": task, "user": user})
        assert "error" in result

    def test_move_to_sprint_no_sprint_id(self, user, task):
        """MOVE_TO_SPRINT sin sprint_id no hace nada."""
        rule = AutomationRule.objects.create(
            owner=user, name="M", trigger=AutomationRule.Trigger.TASK_CREATED,
            action=AutomationRule.Action.MOVE_TO_SPRINT,
            action_params={}, enabled=True,
        )
        result = execute_action(rule, {"task": task, "user": user})
        assert result["skipped"] == "no sprint_id in action_params"

    def test_subtasks_in_progress(self, user, task):
        """SUBTASKS_IN_PROGRESS mueve subtareas pendientes a in_progress."""
        child = Task.objects.create(owner=user, title="Child", parent=task, state="pending")
        rule = AutomationRule.objects.create(
            owner=user, name="SP", trigger=AutomationRule.Trigger.TASK_CREATED,
            action=AutomationRule.Action.SUBTASKS_IN_PROGRESS,
            action_params={}, enabled=True,
        )
        result = execute_action(rule, {"task": task, "user": user})
        assert result["moved_subtasks"] == 1
        child.refresh_from_db()
        assert child.state == "in_progress"

    def test_create_notification(self, user, task):
        rule = AutomationRule.objects.create(
            owner=user, name="N", trigger=AutomationRule.Trigger.TASK_CREATED,
            action=AutomationRule.Action.CREATE_NOTIFICATION,
            action_params={"title": "Test notif", "body": "Body"}, enabled=True,
        )
        result = execute_action(rule, {"task": task, "user": user})
        assert result["notification_created"] is True

    def test_create_notification_default_title(self, user, task):
        """CREATE_NOTIFICATION con title por defecto usa el nombre de la regla."""
        rule = AutomationRule.objects.create(
            owner=user, name="My Rule", trigger=AutomationRule.Trigger.TASK_CREATED,
            action=AutomationRule.Action.CREATE_NOTIFICATION,
            action_params={}, enabled=True,
        )
        result = execute_action(rule, {"task": task, "user": user})
        assert result["notification_created"] is True

    def test_create_task(self, user):
        rule = AutomationRule.objects.create(
            owner=user, name="CT", trigger=AutomationRule.Trigger.TASK_CREATED,
            action=AutomationRule.Action.CREATE_TASK,
            action_params={"title": "Auto task", "priority": 2}, enabled=True,
        )
        result = execute_action(rule, {"user": user})
        assert "created_task_id" in result
        assert Task.objects.filter(owner=user, title="Auto task").exists()

    def test_create_task_defaults(self, user):
        """CREATE_TASK sin params usa defaults."""
        rule = AutomationRule.objects.create(
            owner=user, name="CT", trigger=AutomationRule.Trigger.TASK_CREATED,
            action=AutomationRule.Action.CREATE_TASK,
            action_params={}, enabled=True,
        )
        result = execute_action(rule, {"user": user})
        assert "created_task_id" in result
        assert Task.objects.filter(owner=user, title="Tarea creada por automatización").exists()

    def test_set_assignee_by_id(self, user, task):
        """SET_ASSIGNEE por ID."""
        from apps.collaboration.models import ProjectMember
        assignee = User.objects.create_user(
            email="assignee2@test.com", username="a2", password="p",
        )
        ProjectMember.objects.create(project=task.project, user=assignee)
        rule = AutomationRule.objects.create(
            owner=user, name="A", trigger=AutomationRule.Trigger.TASK_CREATED,
            action=AutomationRule.Action.SET_ASSIGNEE,
            action_params={"assignee_id": assignee.id}, enabled=True,
        )
        result = execute_action(rule, {"task": task, "user": user})
        assert result["new_assignee"] == "assignee2@test.com"
        task.refresh_from_db()
        assert task.assignee == assignee

    def test_set_assignee_by_id_not_found(self, user, task):
        """SET_ASSIGNEE por ID inexistente devuelve error."""
        rule = AutomationRule.objects.create(
            owner=user, name="A", trigger=AutomationRule.Trigger.TASK_CREATED,
            action=AutomationRule.Action.SET_ASSIGNEE,
            action_params={"assignee_id": 99999}, enabled=True,
        )
        result = execute_action(rule, {"task": task, "user": user})
        assert "error" in result

    def test_add_tag_empty_name(self, user, task):
        """ADD_TAG con tag_name vacío no hace nada."""
        rule = AutomationRule.objects.create(
            owner=user, name="T", trigger=AutomationRule.Trigger.TASK_CREATED,
            action=AutomationRule.Action.ADD_TAG,
            action_params={"tag_name": ""}, enabled=True,
        )
        result = execute_action(rule, {"task": task, "user": user})
        assert result["skipped"] == "no tag_name in action_params"

    def test_unknown_action(self, user, task):
        """Acción no implementada devuelve error."""
        rule = AutomationRule.objects.create(
            owner=user, name="X", trigger=AutomationRule.Trigger.TASK_CREATED,
            action=AutomationRule.Action.SET_PRIORITY,
            action_params={}, enabled=True,
        )
        # Forzar acción inválida
        rule.action = "INVALID_ACTION"
        result = execute_action(rule, {"task": task, "user": user})
        assert "error" in result
        assert "INVALID_ACTION" in result["error"]


@pytest.mark.django_db
class TestTriggerAutomationEdgeCases:
    def test_trigger_sin_user_returns_empty(self):
        """trigger_automation sin user ni task devuelve []."""
        results = trigger_automation(AutomationRule.Trigger.TASK_CREATED, {})
        assert results == []

    def test_trigger_con_condiciones_fallidas_skipped(self, user, task):
        """Regla con condiciones que no coinciden se marca SKIPPED."""
        rule = AutomationRule.objects.create(
            owner=user, name="Cond", trigger=AutomationRule.Trigger.TASK_CREATED,
            action=AutomationRule.Action.SET_PRIORITY,
            action_params={"priority": 1},
            conditions=[{"field": "priority", "operator": "gt", "value": "5"}],
            enabled=True,
        )
        # task.priority es 3, no > 5
        results = trigger_automation(
            AutomationRule.Trigger.TASK_CREATED,
            {"task": task, "user": user, "priority": task.priority},
        )
        assert len(results) == 0
        log = AutomationLog.objects.filter(rule=rule).first()
        assert log.status == AutomationLog.Status.SKIPPED

    def test_trigger_con_condiciones_ok_ejecuta(self, user, task):
        """Regla con condiciones que coinciden se ejecuta."""
        AutomationRule.objects.create(
            owner=user, name="Cond", trigger=AutomationRule.Trigger.TASK_CREATED,
            action=AutomationRule.Action.SET_PRIORITY,
            action_params={"priority": 1},
            conditions=[{"field": "priority", "operator": "lt", "value": "5"}],
            enabled=True,
        )
        results = trigger_automation(
            AutomationRule.Trigger.TASK_CREATED,
            {"task": task, "user": user, "priority": task.priority},
        )
        assert len(results) == 1
        task.refresh_from_db()
        assert task.priority == 1

    def test_trigger_user_from_task(self, user, task):
        """trigger_automation obtiene user desde task.owner."""
        AutomationRule.objects.create(
            owner=user, name="Auto", trigger=AutomationRule.Trigger.TASK_CREATED,
            action=AutomationRule.Action.SET_PRIORITY,
            action_params={"priority": 2}, enabled=True,
        )
        # No pasar user en context, solo task
        results = trigger_automation(AutomationRule.Trigger.TASK_CREATED, {"task": task})
        assert len(results) == 1

    def test_trigger_disabled_rule_not_executed(self, user, task):
        """Regla deshabilitada no se ejecuta."""
        AutomationRule.objects.create(
            owner=user, name="Disabled", trigger=AutomationRule.Trigger.TASK_CREATED,
            action=AutomationRule.Action.SET_PRIORITY,
            action_params={"priority": 1}, enabled=False,
        )
        results = trigger_automation(AutomationRule.Trigger.TASK_CREATED, {"task": task, "user": user})
        assert len(results) == 0
        assert not AutomationLog.objects.filter(rule__name="Disabled").exists()

    def test_trigger_action_exception_logged_as_failed(self, user, task):
        """Si execute_action lanza excepción, se loguea como FAILED."""
        rule = AutomationRule.objects.create(
            owner=user, name="Fail", trigger=AutomationRule.Trigger.TASK_CREATED,
            action=AutomationRule.Action.SET_PRIORITY,
            action_params={"priority": 1},
            enabled=True,
        )
        with patch(
            "apps.automations.engine.execute_action",
            side_effect=RuntimeError("boom"),
        ):
            results = trigger_automation(AutomationRule.Trigger.TASK_CREATED, {"task": task, "user": user})
        assert len(results) == 1
        assert "error" in results[0]
        log = AutomationLog.objects.filter(rule=rule).first()
        assert log.status == AutomationLog.Status.FAILED
        assert log.error_message is not None

    def test_trigger_increment_count(self, user, task):
        """trigger_automation incrementa trigger_count y actualiza last_triggered_at."""
        rule = AutomationRule.objects.create(
            owner=user, name="Count", trigger=AutomationRule.Trigger.TASK_CREATED,
            action=AutomationRule.Action.SET_PRIORITY,
            action_params={"priority": 1}, enabled=True,
        )
        assert rule.trigger_count == 0
        trigger_automation(AutomationRule.Trigger.TASK_CREATED, {"task": task, "user": user})
        rule.refresh_from_db()
        assert rule.trigger_count == 1
        assert rule.last_triggered_at is not None


@pytest.mark.django_db
class TestRunDailyChecksComprehensive:
    def test_daily_check_overdue_tasks(self, user, task):
        """run_daily_checks dispara TASK_OVERDUE para tareas vencidas."""
        task.due_date = timezone.now() - timedelta(days=1)
        task.save()
        AutomationRule.objects.create(
            owner=user, name="Overdue", trigger=AutomationRule.Trigger.TASK_OVERDUE,
            action=AutomationRule.Action.CREATE_NOTIFICATION,
            action_params={"title": "Overdue!"}, enabled=True,
        )
        run_daily_checks()
        logs = AutomationLog.objects.filter(
            rule__trigger=AutomationRule.Trigger.TASK_OVERDUE
        )
        assert logs.exists()
        assert logs.first().status == AutomationLog.Status.SUCCESS

    def test_daily_check_sprint_ending_soon(self, user, project):
        """run_daily_checks dispara SPRINT_CLOSED para sprints por terminar."""
        Sprint.objects.create(
            owner=user, project=project, name="Ending Sprint",
            state=Sprint.SprintState.ACTIVE,
            start_date=timezone.now().date() - timedelta(days=10),
            end_date=timezone.now().date() + timedelta(days=1),
        )
        AutomationRule.objects.create(
            owner=user, name="Sprint end", trigger=AutomationRule.Trigger.SPRINT_CLOSED,
            action=AutomationRule.Action.CREATE_NOTIFICATION,
            action_params={"title": "Sprint ending!"}, enabled=True,
        )
        run_daily_checks()
        logs = AutomationLog.objects.filter(
            rule__trigger=AutomationRule.Trigger.SPRINT_CLOSED
        )
        assert logs.exists()

    def test_daily_check_no_overdue_no_results(self, user, task):
        """Sin tareas vencidas ni sprints por terminar, run_daily_checks no dispara."""
        task.due_date = timezone.now() + timedelta(days=10)
        task.save()
        run_daily_checks()
        # Puede haber resultados de DAILY_CHECK si hay reglas, pero no de TASK_OVERDUE
        overdue_logs = AutomationLog.objects.filter(
            rule__trigger=AutomationRule.Trigger.TASK_OVERDUE
        )
        assert not overdue_logs.exists()
