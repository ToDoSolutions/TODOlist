"""Tests exhaustivos para integrations/signals.py."""
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model

from apps.integrations.models import GitHubInstallation, GitHubIssueLink, GitHubRepo
from apps.projects.models import Project
from apps.tasks.models import Task

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="is", email="is@is.com", password="pass")


@pytest.fixture
def project(user, db):
    return Project.objects.create(owner=user, name="Test Project")


@pytest.fixture
def repo(user, db):
    installation = GitHubInstallation.objects.create(user=user, installation_id=123)
    return GitHubRepo.objects.create(
        installation=installation, repo_id=456, full_name="org/repo", name="repo", owner="org"
    )


@pytest.mark.django_db
class TestSyncTaskToGitHub:
    def test_no_link_no_sync(self, user, project):
        """Verifica que no sincroniza si la tarea no tiene link de GitHub."""
        with patch("apps.integrations.sync_service.sync_task_to_issue") as mock_sync:
            Task.objects.create(owner=user, project=project, title="Task")
            mock_sync.assert_not_called()

    def test_sync_with_link(self, user, project, repo):
        """Verifica que sincroniza si la tarea tiene link de GitHub."""
        task = Task.objects.create(owner=user, project=project, title="Task")
        GitHubIssueLink.objects.create(
            task=task, repo=repo, issue_number=1, issue_id=100
        )
        with patch("apps.integrations.sync_service.sync_task_to_issue") as mock_sync:
            task.title = "Updated"
            task.save()
            mock_sync.assert_called_once_with(task)

    def test_no_sync_when_syncing(self, user, project, repo):
        """Verifica que no sincroniza si estamos en medio de un sync."""
        task = Task.objects.create(owner=user, project=project, title="Task")
        GitHubIssueLink.objects.create(
            task=task, repo=repo, issue_number=1, issue_id=100
        )
        task._syncing_from_github = True
        with patch("apps.integrations.sync_service.sync_task_to_issue") as mock_sync:
            task.save()
            mock_sync.assert_not_called()

    def test_sync_error_logged(self, user, project, repo):
        """Verifica que errores de sync se loggean pero no rompen el save."""
        task = Task.objects.create(owner=user, project=project, title="Task")
        GitHubIssueLink.objects.create(
            task=task, repo=repo, issue_number=1, issue_id=100
        )
        with patch("apps.integrations.sync_service.sync_task_to_issue", side_effect=Exception("fail")):
            task.title = "Updated"
            task.save()  # No debe lanzar excepción
            assert Task.objects.get(id=task.id).title == "Updated"
