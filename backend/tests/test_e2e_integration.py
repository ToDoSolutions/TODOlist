"""Tests E2E/integración con mocks para OAuth GitHub, Slack, Discord y descarga real."""
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.integrations_chat.models import ChatIntegration
from apps.tasks.models import Attachment, Task

User = get_user_model()


@pytest.fixture
def authed_client(user):
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return client


# --- OAuth providers ---

@pytest.mark.django_db
class TestOAuthProviders:
    def test_oauth_providers_endpoint(self, api_client):
        """GET /api/auth/oauth-providers/ retorna providers configurados."""
        resp = api_client.get("/api/auth/oauth-providers/")
        assert resp.status_code == 200
        data = resp.data if hasattr(resp, "data") else resp.json()
        assert "github" in data
        assert "google" in data

    @patch("apps.integrations.views.GitHubOAuthClient")
    def test_github_oauth_start_returns_auth_url(self, mock_oauth_class, api_client):
        """GET /api/auth/github/start/ retorna auth_url y state."""
        mock_oauth = MagicMock()
        mock_oauth.get_authorize_url.return_value = "https://github.com/login/oauth/authorize?client_id=test"
        mock_oauth_class.return_value = mock_oauth

        resp = api_client.get("/api/auth/github/start/")
        assert resp.status_code == 200
        data = resp.data if hasattr(resp, "data") else resp.json()
        assert "auth_url" in data
        assert "state" in data
        assert "github.com" in data["auth_url"]

    @patch("apps.integrations.views.GitHubOAuthClient")
    def test_github_oauth_callback_invalid_state(self, mock_oauth_class, api_client):
        """POST callback con state inválido devuelve 400."""
        resp = api_client.post("/api/auth/github/callback/", {
            "code": "test_code",
            "state": "invalid_state",
        })
        assert resp.status_code == 400

    @patch("apps.integrations.views.GitHubOAuthClient")
    def test_github_oauth_callback_success(self, mock_oauth_class, api_client):
        """POST callback con code válido crea/linkea usuario y retorna token."""
        # Configurar session con state válido
        session = api_client.session
        session["github_oauth_state"] = "valid_state"
        session.save()

        mock_oauth = MagicMock()
        mock_oauth.exchange_code.return_value = {"access_token": "gho_test_token"}
        mock_oauth.get_user_info.return_value = {
            "id": 12345,
            "login": "testuser",
            "email": "githubuser@test.com",
            "name": "Test User",
            "avatar_url": "https://github.com/avatar.png",
        }
        mock_oauth_class.return_value = mock_oauth

        resp = api_client.post("/api/auth/github/callback/", {
            "code": "test_code",
            "state": "valid_state",
        }, format="json")
        # Puede ser 200 (login) o 201 (registro)
        assert resp.status_code in (200, 201)
        data = resp.data if hasattr(resp, "data") else resp.json()
        assert "access" in data or "token" in data or "user" in data


# --- Slack integration ---

@pytest.mark.django_db
class TestSlackIntegration:
    @patch("apps.integrations_chat.services.requests.post")
    def test_slack_send_message_success(self, mock_post, authed_client, user):
        """POST /api/chat-integrations/{id}/test/ envía mensaje a Slack."""
        # Crear integración
        integration = ChatIntegration.objects.create(
            owner=user,
            provider="slack",
            webhook_url="https://hooks.slack.com/services/test",
        )
        # Mock respuesta de Slack
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "OK"
        mock_post.return_value = mock_resp

        resp = authed_client.post(f"/api/chat-integrations/{integration.id}/test/")
        assert resp.status_code == 200
        data = resp.data if hasattr(resp, "data") else resp.json()
        assert data["success"] is True
        assert data["status_code"] == 200
        # Verificar que se llamó a Slack
        mock_post.assert_called_once()

    @patch("apps.integrations_chat.services.requests.post")
    def test_slack_send_message_failure(self, mock_post, authed_client, user):
        """Si Slack devuelve error, success=False."""
        integration = ChatIntegration.objects.create(
            owner=user,
            provider="slack",
            webhook_url="https://hooks.slack.com/services/test",
        )
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Error"
        mock_post.return_value = mock_resp

        resp = authed_client.post(f"/api/chat-integrations/{integration.id}/test/")
        assert resp.status_code == 200
        data = resp.data if hasattr(resp, "data") else resp.json()
        assert data["success"] is False
        assert data["status_code"] == 500


# --- Discord integration ---

@pytest.mark.django_db
class TestDiscordIntegration:
    @patch("apps.integrations_chat.services.requests.post")
    def test_discord_send_message_success(self, mock_post, authed_client, user):
        """POST /api/chat-integrations/{id}/test/ envía mensaje a Discord."""
        integration = ChatIntegration.objects.create(
            owner=user,
            provider="discord",
            webhook_url="https://discord.com/api/webhooks/test",
        )
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_resp.text = ""
        mock_post.return_value = mock_resp

        resp = authed_client.post(f"/api/chat-integrations/{integration.id}/test/")
        assert resp.status_code == 200
        data = resp.data if hasattr(resp, "data") else resp.json()
        assert data["success"] is True
        assert data["status_code"] == 204

    @patch("apps.integrations_chat.services.requests.post")
    def test_discord_send_message_network_error(self, mock_post, authed_client, user):
        """Si hay error de red, success=False y error contiene el mensaje."""
        integration = ChatIntegration.objects.create(
            owner=user,
            provider="discord",
            webhook_url="https://discord.com/api/webhooks/test",
        )
        mock_post.side_effect = ConnectionError("Network unreachable")

        resp = authed_client.post(f"/api/chat-integrations/{integration.id}/test/")
        assert resp.status_code == 200
        data = resp.data if hasattr(resp, "data") else resp.json()
        assert data["success"] is False
        assert data["error"]


# --- Attachment download real ---

@pytest.mark.django_db
class TestAttachmentDownloadReal:
    def test_download_real_file_content(self, authed_client, user, task):
        """El endpoint download/ devuelve el contenido real del archivo."""
        content = b"Hello World! This is a test file."
        att = Attachment.objects.create(
            task=task,
            uploaded_by=user,
            file=SimpleUploadedFile("test_download.txt", content, content_type="text/plain"),
            filename="test_download.txt",
            file_size=len(content),
            content_type="text/plain",
        )
        resp = authed_client.get(f"/api/attachments/{att.id}/download/")
        assert resp.status_code == 200
        assert "attachment" in resp.get("Content-Disposition", "")
        # El contenido debe ser el original
        streaming_content = b"".join(resp.streaming_content) if hasattr(resp, "streaming_content") else resp.content
        assert streaming_content == content

    def test_download_nonexistent_attachment_404(self, authed_client):
        """GET download/ para attachment inexistente devuelve 404."""
        resp = authed_client.get("/api/attachments/99999/download/")
        assert resp.status_code == 404

    def test_download_attachment_from_other_user_404(self, authed_client, user, other_user, task):
        """Usuario B no puede descargar attachment de tarea de Usuario A."""
        # Crear tarea de other_user
        from apps.projects.models import Project
        project_b = Project.objects.create(owner=other_user, name="Project B")
        task_b = Task.objects.create(
            owner=other_user,
            project=project_b,
            title="Task B",
        )
        att = Attachment.objects.create(
            task=task_b,
            uploaded_by=other_user,
            file=SimpleUploadedFile("private.txt", b"secret", content_type="text/plain"),
            filename="private.txt",
            file_size=6,
            content_type="text/plain",
        )
        # user intenta descargar attachment de other_user
        resp = authed_client.get(f"/api/attachments/{att.id}/download/")
        assert resp.status_code == 404


# --- User account management ---

@pytest.mark.django_db
class TestUserAccountManagement:
    def test_get_me(self, authed_client, user):
        """GET /api/users/me/ retorna info del usuario actual."""
        resp = authed_client.get("/api/users/me/")
        assert resp.status_code == 200
        data = resp.data if hasattr(resp, "data") else resp.json()
        assert data["email"] == user.email
        assert data["is_active"] is True

    def test_deactivate_account(self, authed_client, user):
        """POST /api/users/me/deactivate/ desactiva la cuenta."""
        resp = authed_client.post("/api/users/me/deactivate/", {"password": "testpass123"})
        assert resp.status_code == 200
        user.refresh_from_db()
        assert user.is_active is False

    def test_delete_account_without_confirm(self, authed_client, user):
        """DELETE /api/users/me/delete_account/ sin ?confirm=true devuelve 400."""
        resp = authed_client.delete("/api/users/me/delete_account/")
        assert resp.status_code == 400

    def test_delete_account_with_confirm(self, authed_client, user):
        """DELETE /api/users/me/delete_account/?confirm=true elimina la cuenta."""
        user_id = user.id
        resp = authed_client.delete("/api/users/me/delete_account/?confirm=true", {"password": "testpass123"})
        assert resp.status_code == 204
        assert not User.objects.filter(id=user_id).exists()


# --- SavedSearch update ---

@pytest.mark.django_db
class TestSavedSearchUpdate:
    def test_update_saved_search_name(self, authed_client, user):
        """PATCH /api/saved-searches/{id}/ actualiza el nombre."""
        from apps.tasks.models import SavedSearch
        ss = SavedSearch.objects.create(
            owner=user,
            name="Búsqueda original",
            filters="{}",
        )
        resp = authed_client.patch(f"/api/saved-searches/{ss.id}/", {"name": "Búsqueda renombrada"})
        assert resp.status_code == 200
        ss.refresh_from_db()
        assert ss.name == "Búsqueda renombrada"

    def test_update_saved_search_other_user_404(self, authed_client, other_user):
        """Usuario A no puede editar búsqueda de Usuario B."""
        from apps.tasks.models import SavedSearch
        ss = SavedSearch.objects.create(
            owner=other_user,
            name="Búsqueda de B",
            filters="{}",
        )
        resp = authed_client.patch(f"/api/saved-searches/{ss.id}/", {"name": "Hackeado"})
        assert resp.status_code == 404


# --- ProjectMember update/remove ---

@pytest.mark.django_db
class TestProjectMemberUpdateRemove:
    def test_update_member_role(self, authed_client, user, other_user, project):
        """PATCH /api/project-members/{id}/ cambia el rol."""
        from apps.collaboration.models import ProjectMember
        member = ProjectMember.objects.create(
            project=project,
            user=other_user,
            role="viewer",
        )
        resp = authed_client.patch(f"/api/project-members/{member.id}/", {"role": "editor"})
        assert resp.status_code == 200, f"Response: {resp.data if hasattr(resp, 'data') else resp.json()}"
        member.refresh_from_db()
        assert member.role == "editor"

    def test_remove_member(self, authed_client, user, other_user, project):
        """DELETE /api/project-members/{id}/ elimina el miembro."""
        from apps.collaboration.models import ProjectMember
        member = ProjectMember.objects.create(
            project=project,
            user=other_user,
            role="member",
        )
        resp = authed_client.delete(f"/api/project-members/{member.id}/")
        assert resp.status_code == 204
        assert not ProjectMember.objects.filter(id=member.id).exists()
