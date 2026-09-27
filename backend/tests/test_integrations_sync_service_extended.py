"""Tests exhaustivos para integrations/sync_service.py."""
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model

from apps.integrations.models import GitHubInstallation, GitHubIssueLink, GitHubRepo
from apps.integrations.sync_service import (
    create_issue_for_task,
    import_issue_as_task,
    sync_issue_to_task,
    sync_task_to_issue,
)
from apps.projects.models import Project
from apps.tasks.models import Task

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="ss", email="ss@ss.com", password="pass")


@pytest.fixture
def project(user, db):
    return Project.objects.create(owner=user, name="Test Project")


@pytest.fixture
def repo(user, db):
    installation = GitHubInstallation.objects.create(user=user, installation_id=123)
    return GitHubRepo.objects.create(
        installation=installation, repo_id=456, full_name="org/repo", name="repo", owner="org"
    )


@pytest.fixture
def linked_task(user, project, repo, db):
    task = Task.objects.create(owner=user, project=project, title="Task")
    GitHubIssueLink.objects.create(task=task, repo=repo, issue_number=1, issue_id=100)
    return task


@pytest.mark.django_db
class TestSyncTaskToIssue:
    def test_no_link_returns_none(self, user, project):
        task = Task.objects.create(owner=user, project=project, title="Task")
        assert sync_task_to_issue(task) is None

    def test_syncs_to_github(self, linked_task, repo):
        with patch("apps.integrations.sync_service.GitHubAppClient") as mock_client:
            mock_instance = mock_client.return_value
            mock_instance.update_issue.return_value = {"state": "open"}
            link = sync_task_to_issue(linked_task)
            assert link.issue_state == "open"
            mock_instance.update_issue.assert_called_once()

    def test_completed_task_closes_issue(self, user, project, repo):
        task = Task.objects.create(owner=user, project=project, title="Done", state="completed")
        GitHubIssueLink.objects.create(task=task, repo=repo, issue_number=1, issue_id=100)
        with patch("apps.integrations.sync_service.GitHubAppClient") as mock_client:
            mock_instance = mock_client.return_value
            mock_instance.update_issue.return_value = {"state": "closed"}
            link = sync_task_to_issue(task)
            assert link.issue_state == "closed"
            call_kwargs = mock_instance.update_issue.call_args
            assert call_kwargs.kwargs["state"] == "closed" or call_kwargs[1]["state"] == "closed"


@pytest.mark.django_db
class TestSyncIssueToTask:
    def test_updates_title(self, linked_task):
        link = linked_task.github_link
        sync_issue_to_task(link, {"title": "New Title", "state": "open"})
        linked_task.refresh_from_db()
        assert linked_task.title == "New Title"

    def test_closes_task(self, linked_task):
        link = linked_task.github_link
        sync_issue_to_task(link, {"title": "Task", "state": "closed"})
        linked_task.refresh_from_db()
        assert linked_task.state == "completed"
        assert linked_task.completed_at is not None

    def test_reopens_task(self, user, project, repo):
        task = Task.objects.create(owner=user, project=project, title="Task", state="completed")
        GitHubIssueLink.objects.create(task=task, repo=repo, issue_number=1, issue_id=100)
        link = task.github_link
        sync_issue_to_task(link, {"title": "Task", "state": "open"})
        task.refresh_from_db()
        assert task.state == "pending"
        assert task.completed_at is None

    def test_updates_link_metadata(self, linked_task):
        link = linked_task.github_link
        sync_issue_to_task(link, {"title": "Task", "state": "open", "html_url": "http://x"})
        link.refresh_from_db()
        assert link.issue_url == "http://x"


@pytest.mark.django_db
class TestCreateIssueForTask:
    def test_creates_issue_and_link(self, user, project, repo):
        task = Task.objects.create(owner=user, project=project, title="Task")
        with patch("apps.integrations.sync_service.GitHubAppClient") as mock_client:
            mock_instance = mock_client.return_value
            mock_instance.create_issue.return_value = {
                "number": 5, "id": 500, "html_url": "http://x", "state": "open"
            }
            link = create_issue_for_task(task, repo)
            assert link.issue_number == 5
            assert link.issue_id == 500
            assert task.github_link == link


@pytest.mark.django_db
class TestImportIssueAsTask:
    def test_creates_task(self, user, repo):
        issue = {"id": 100, "number": 1, "title": "Bug", "state": "open", "body": "Desc"}
        task, created = import_issue_as_task(issue, repo, user)
        assert created is True
        assert task.title == "Bug"
        assert task.github_link.issue_number == 1

    def test_no_duplicate(self, user, repo):
        issue = {"id": 100, "number": 1, "title": "Bug", "state": "open"}
        import_issue_as_task(issue, repo, user)
        _, created = import_issue_as_task(issue, repo, user)
        assert created is False

    def test_closed_issue_maps_to_completed(self, user, repo):
        issue = {"id": 100, "number": 1, "title": "Bug", "state": "closed"}
        task, _ = import_issue_as_task(issue, repo, user)
        assert task.state == "completed"
