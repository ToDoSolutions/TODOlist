from unittest.mock import patch

import pytest
import requests
from django.contrib.auth import get_user_model
from django.utils import timezone

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
    _parse_iso,
    sync_check_runs,
    sync_commits,
    sync_pull_requests,
    sync_releases,
    sync_repo_data,
)
from apps.integrations.sync_service import (
    create_issue_for_task,
    import_issue_as_task,
    sync_issue_to_task,
    sync_repo_issues,
    sync_task_to_issue,
)
from apps.tasks.models import Task

User = get_user_model()


@pytest.mark.django_db
class TestParseIso:
    def test_valid(self):
        assert _parse_iso("2024-01-01T12:00:00Z") is not None
        assert _parse_iso("2024-01-01T12:00:00+00:00") is not None

    def test_invalid(self):
        assert _parse_iso("") is None
        assert _parse_iso(None) is None
        assert _parse_iso("invalid") is None


@pytest.mark.django_db
class TestSyncGitHub:
    @pytest.fixture(autouse=True)
    def setup_data(self, db):
        self.user = User.objects.create_user(username="sg", email="sg@sg.com", password="pass")
        self.inst = GitHubInstallation.objects.create(user=self.user, installation_id=1)
        self.repo = GitHubRepo.objects.create(installation=self.inst, repo_id=1, full_name="a/b", name="b", owner="a")

    def test_sync_pull_requests(self):
        with patch("apps.integrations.sync_github._get_client") as mock_client:
            mock_client.return_value.list_pull_requests.return_value = [
                {"id": 1, "number": 1, "title": "PR1", "state": "open", "body": "Fixes #1"},
                {"id": 2, "number": 2, "title": "PR2", "state": "closed", "merged": True},
            ]
            count = sync_pull_requests(self.repo, self.inst)
            assert count == 2
            assert GitHubPullRequest.objects.filter(repo=self.repo).count() == 2

    def test_sync_pull_requests_error(self):
        with patch("apps.integrations.sync_github._get_client") as mock_client:
            mock_client.return_value.list_pull_requests.side_effect = (
                requests.ConnectionError("API error")
            )
            count = sync_pull_requests(self.repo, self.inst)
            assert count == 0

    def test_sync_commits(self):
        with patch("apps.integrations.sync_github._get_client") as mock_client:
            mock_client.return_value.list_commits.return_value = [
                {"sha": "abc", "commit": {"message": "msg", "author": {"name": "a", "date": "2024-01-01T00:00:00Z"}}},
            ]
            count = sync_commits(self.repo, self.inst)
            assert count == 1
            assert GitHubCommit.objects.filter(sha="abc").exists()

    def test_sync_commits_error(self):
        with patch("apps.integrations.sync_github._get_client") as mock_client:
            mock_client.return_value.list_commits.side_effect = (
                requests.ConnectionError("API error")
            )
            count = sync_commits(self.repo, self.inst)
            assert count == 0

    def test_sync_releases(self):
        with patch("apps.integrations.sync_github._get_client") as mock_client:
            mock_client.return_value.list_releases.return_value = [
                {"id": 10, "tag_name": "v1.0", "name": "Release", "author": {"login": "a"}},
            ]
            count = sync_releases(self.repo, self.inst)
            assert count == 1
            assert GitHubRelease.objects.filter(release_id=10).exists()

    def test_sync_check_runs(self):
        with patch("apps.integrations.sync_github._get_client") as mock_client:
            mock_client.return_value.list_check_runs.return_value = [
                {"id": 5, "name": "CI", "status": "completed", "conclusion": "success", "head_sha": "abc"},
            ]
            count = sync_check_runs(self.repo, self.inst)
            assert count == 1
            assert GitHubCheckRun.objects.filter(check_id=5).exists()

    def test_sync_repo_data(self):
        self.repo.sync_enabled = True
        self.repo.save()
        with patch("apps.integrations.sync_github.sync_pull_requests", return_value=2), \
             patch("apps.integrations.sync_github.sync_commits", return_value=3), \
             patch("apps.integrations.sync_github.sync_releases", return_value=1), \
             patch("apps.integrations.sync_github.sync_check_runs", return_value=4):
            result = sync_repo_data(self.repo)
            assert result == {"pull_requests": 2, "commits": 3, "releases": 1, "check_runs": 4}

    def test_sync_repo_data_disabled(self):
        self.repo.sync_enabled = False
        self.repo.save()
        result = sync_repo_data(self.repo)
        assert result == {"pull_requests": 0, "commits": 0, "releases": 0, "check_runs": 0}


@pytest.mark.django_db
class TestSyncService:
    @pytest.fixture(autouse=True)
    def setup_data(self, db):
        self.user = User.objects.create_user(username="ss", email="ss@ss.com", password="pass")
        self.inst = GitHubInstallation.objects.create(user=self.user, installation_id=1)
        self.repo = GitHubRepo.objects.create(installation=self.inst, repo_id=1, full_name="a/b", name="b", owner="a")
        self.task = Task.objects.create(owner=self.user, title="T", state="pending")

    def test_sync_task_to_issue(self):
        link = GitHubIssueLink.objects.create(task=self.task, repo=self.repo, issue_number=1, issue_id=100, issue_url="http://x", issue_state="open")
        with patch("apps.integrations.sync_service.GitHubAppClient") as mock_client:
            mock_client.return_value.update_issue.return_value = {"state": "open"}
            result = sync_task_to_issue(self.task)
            assert result == link
            link.refresh_from_db()
            assert link.issue_state == "open"

    def test_sync_task_to_issue_no_link(self):
        assert sync_task_to_issue(self.task) is None

    def test_sync_issue_to_task(self):
        link = GitHubIssueLink.objects.create(task=self.task, repo=self.repo, issue_number=1, issue_id=100, issue_url="http://x", issue_state="open")
        sync_issue_to_task(link, {"title": "New Title", "state": "closed", "html_url": "http://new"})
        self.task.refresh_from_db()
        assert self.task.title == "New Title"
        assert self.task.state == "completed"
        assert self.task.completed_at is not None
        link.refresh_from_db()
        assert link.issue_state == "closed"

    def test_sync_issue_to_task_reopen(self):
        self.task.state = "completed"
        self.task.completed_at = timezone.now()
        self.task.save()
        link = GitHubIssueLink.objects.create(task=self.task, repo=self.repo, issue_number=1, issue_id=100, issue_url="http://x", issue_state="closed")
        sync_issue_to_task(link, {"state": "open"})
        self.task.refresh_from_db()
        assert self.task.state == "pending"
        assert self.task.completed_at is None

    def test_create_issue_for_task(self):
        with patch("apps.integrations.sync_service.GitHubAppClient") as mock_client:
            mock_client.return_value.create_issue.return_value = {"number": 5, "id": 500, "html_url": "http://x", "state": "open"}
            link = create_issue_for_task(self.task, self.repo)
            assert link.issue_number == 5
            assert link.issue_id == 500
            assert link.task == self.task

    def test_import_issue_as_task(self):
        task, created = import_issue_as_task({"number": 1, "id": 100, "title": "Issue", "body": "Body", "state": "open", "html_url": "http://x"}, self.repo, self.user)
        assert created is True
        assert task.title == "Issue"
        assert task.owner == self.user
        assert GitHubIssueLink.objects.filter(task=task, issue_number=1).exists()

    def test_import_issue_as_task_duplicate(self):
        GitHubIssueLink.objects.create(task=self.task, repo=self.repo, issue_number=1, issue_id=100)
        task, created = import_issue_as_task({"number": 1, "id": 100, "title": "Issue", "state": "open"}, self.repo, self.user)
        assert created is False
        assert task == self.task

    def test_sync_repo_issues(self):
        GitHubIssueLink.objects.create(task=self.task, repo=self.repo, issue_number=1, issue_id=100)
        with patch("apps.integrations.sync_service.GitHubAppClient") as mock_client:
            mock_client.return_value.list_issues.return_value = [
                {"number": 1, "title": "T", "state": "open"},
                {"number": 2, "title": "PR", "state": "open", "pull_request": {}},
            ]
            count = sync_repo_issues(self.repo)
            assert count == 1
