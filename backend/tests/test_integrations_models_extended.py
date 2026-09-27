"""Tests exhaustivos para modelos de integrations."""
import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

from apps.integrations.models import (
    GitHubCheckRun,
    GitHubCommit,
    GitHubInstallation,
    GitHubIssueLink,
    GitHubPullRequest,
    GitHubRelease,
    GitHubRepo,
    WebhookDelivery,
)

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="gh", email="gh@gh.com", password="pass")


@pytest.mark.django_db
class TestWebhookDelivery:
    def test_str(self):
        d = WebhookDelivery.objects.create(
            delivery_id="abc123", event_type="issues", action="opened",
        )
        assert "abc123" in str(d)
        assert "issues" in str(d)
        assert "opened" in str(d)

    def test_status_choices(self):
        assert WebhookDelivery.Status.PENDING == "pending"
        assert WebhookDelivery.Status.PROCESSED == "processed"
        assert WebhookDelivery.Status.FAILED == "failed"
        assert WebhookDelivery.Status.RETRYING == "retrying"
        assert WebhookDelivery.Status.DEAD_LETTER == "dead_letter"

    def test_is_dead(self):
        d = WebhookDelivery.objects.create(
            delivery_id="abc123", event_type="issues", status="dead_letter"
        )
        assert d.is_dead is True
        d.status = "pending"
        assert d.is_dead is False

    def test_can_retry(self):
        d = WebhookDelivery.objects.create(
            delivery_id="abc123", event_type="issues", retry_count=0, max_retries=5
        )
        assert d.can_retry is True
        d.retry_count = 5
        assert d.can_retry is False
        d.retry_count = 0
        d.status = "dead_letter"
        assert d.can_retry is False

    def test_defaults(self):
        d = WebhookDelivery.objects.create(delivery_id="abc123", event_type="issues")
        assert d.action == ""
        assert d.payload == {}
        assert d.status == "pending"
        assert d.error_message == ""
        assert d.retry_count == 0
        assert d.max_retries == 5
        assert d.repo_full_name == ""

    def test_unique_delivery_id(self):
        WebhookDelivery.objects.create(delivery_id="abc123", event_type="issues")
        with pytest.raises(IntegrityError):
            WebhookDelivery.objects.create(delivery_id="abc123", event_type="issues")

    def test_ordering(self):
        d1 = WebhookDelivery.objects.create(delivery_id="1", event_type="a")
        d2 = WebhookDelivery.objects.create(delivery_id="2", event_type="b")
        from django.utils import timezone as _tz
        WebhookDelivery.objects.filter(pk=d1.pk).update(created_at=_tz.now() - _tz.timedelta(hours=1))
        deliveries = list(WebhookDelivery.objects.all())
        assert deliveries[0] == d2  # ordering by -created_at


@pytest.mark.django_db
class TestGitHubInstallation:
    def test_str(self, user):
        inst = GitHubInstallation.objects.create(
            user=user, installation_id=12345, account_login="testorg"
        )
        assert "testorg" in str(inst)
        assert "12345" in str(inst)

    def test_defaults(self, user):
        inst = GitHubInstallation.objects.create(
            user=user, installation_id=12345, account_login="testorg"
        )
        assert inst.account_type == "User"
        assert inst.avatar_url == ""
        assert inst.github_user_id is None
        assert inst.github_username == ""
        assert inst.access_token == ""
        assert inst.refresh_token == ""
        assert inst.token_expires_at is None

    def test_unique_installation_id(self, user):
        GitHubInstallation.objects.create(
            user=user, installation_id=12345, account_login="testorg"
        )
        with pytest.raises(IntegrityError):
            GitHubInstallation.objects.create(
                user=user, installation_id=12345, account_login="other"
            )


@pytest.mark.django_db
class TestGitHubRepo:
    def test_str(self, user):
        inst = GitHubInstallation.objects.create(
            user=user, installation_id=12345, account_login="testorg"
        )
        repo = GitHubRepo.objects.create(
            installation=inst, repo_id=67890, full_name="org/repo", name="repo", owner="org"
        )
        assert str(repo) == "org/repo"

    def test_defaults(self, user):
        inst = GitHubInstallation.objects.create(
            user=user, installation_id=12345, account_login="testorg"
        )
        repo = GitHubRepo.objects.create(
            installation=inst, repo_id=67890, full_name="org/repo", name="repo", owner="org"
        )
        assert repo.is_private is False
        assert repo.sync_enabled is True
        assert repo.default_branch == "main"

    def test_unique_together(self, user):
        inst = GitHubInstallation.objects.create(
            user=user, installation_id=12345, account_login="testorg"
        )
        GitHubRepo.objects.create(
            installation=inst, repo_id=67890, full_name="org/repo", name="repo", owner="org"
        )
        with pytest.raises(IntegrityError):
            GitHubRepo.objects.create(
                installation=inst, repo_id=67890, full_name="org/repo2", name="repo2", owner="org"
            )


@pytest.mark.django_db
class TestGitHubIssueLink:
    def test_str(self, user):
        inst = GitHubInstallation.objects.create(
            user=user, installation_id=12345, account_login="testorg"
        )
        repo = GitHubRepo.objects.create(
            installation=inst, repo_id=67890, full_name="org/repo", name="repo", owner="org"
        )
        from apps.tasks.models import Task
        task = Task.objects.create(owner=user, title="Task 1")
        link = GitHubIssueLink.objects.create(
            task=task, repo=repo, issue_number=42, issue_id=98765, issue_url="https://github.com/org/repo/issues/42"
        )
        assert "org/repo#42" in str(link)
        assert "Task 1" in str(link)

    def test_defaults(self, user):
        inst = GitHubInstallation.objects.create(
            user=user, installation_id=12345, account_login="testorg"
        )
        repo = GitHubRepo.objects.create(
            installation=inst, repo_id=67890, full_name="org/repo", name="repo", owner="org"
        )
        from apps.tasks.models import Task
        task = Task.objects.create(owner=user, title="Task 1")
        link = GitHubIssueLink.objects.create(
            task=task, repo=repo, issue_number=42, issue_id=98765, issue_url="https://github.com/org/repo/issues/42"
        )
        assert link.issue_state == "open"
        assert link.last_synced_at is None
        assert link.project_node_id == ""
        assert link.project_status == ""


@pytest.mark.django_db
class TestGitHubPullRequest:
    def test_str(self, user):
        inst = GitHubInstallation.objects.create(
            user=user, installation_id=12345, account_login="testorg"
        )
        repo = GitHubRepo.objects.create(
            installation=inst, repo_id=67890, full_name="org/repo", name="repo", owner="org"
        )
        pr = GitHubPullRequest.objects.create(
            repo=repo, pr_number=123, pr_id=456789, title="PR Title", html_url="https://github.com/org/repo/pull/123"
        )
        assert "org/repo#123" in str(pr)
        assert "open" in str(pr)

    def test_defaults(self, user):
        inst = GitHubInstallation.objects.create(
            user=user, installation_id=12345, account_login="testorg"
        )
        repo = GitHubRepo.objects.create(
            installation=inst, repo_id=67890, full_name="org/repo", name="repo", owner="org"
        )
        pr = GitHubPullRequest.objects.create(
            repo=repo, pr_number=123, pr_id=456789, title="PR Title", html_url="https://github.com/org/repo/pull/123"
        )
        assert pr.state == "open"
        assert pr.is_merged is False
        assert pr.is_draft is False
        assert pr.head_branch == ""
        assert pr.base_branch == ""
        assert pr.author == ""
        assert pr.review_comments_count == 0
        assert pr.approvals_count == 0
        assert pr.changes_requested is False
        assert pr.ci_status == ""
        assert pr.ci_url == ""


@pytest.mark.django_db
class TestGitHubCommit:
    def test_str(self, user):
        inst = GitHubInstallation.objects.create(
            user=user, installation_id=12345, account_login="testorg"
        )
        repo = GitHubRepo.objects.create(
            installation=inst, repo_id=67890, full_name="org/repo", name="repo", owner="org"
        )
        commit = GitHubCommit.objects.create(
            repo=repo, sha="abc123def456", message="fix bug"
        )
        assert "abc123de" in str(commit)
        assert "org/repo" in str(commit)

    def test_unique_sha(self, user):
        inst = GitHubInstallation.objects.create(
            user=user, installation_id=12345, account_login="testorg"
        )
        repo = GitHubRepo.objects.create(
            installation=inst, repo_id=67890, full_name="org/repo", name="repo", owner="org"
        )
        GitHubCommit.objects.create(repo=repo, sha="abc123", message="fix")
        with pytest.raises(IntegrityError):
            GitHubCommit.objects.create(repo=repo, sha="abc123", message="fix2")


@pytest.mark.django_db
class TestGitHubRelease:
    def test_str(self, user):
        inst = GitHubInstallation.objects.create(
            user=user, installation_id=12345, account_login="testorg"
        )
        repo = GitHubRepo.objects.create(
            installation=inst, repo_id=67890, full_name="org/repo", name="repo", owner="org"
        )
        release = GitHubRelease.objects.create(
            repo=repo, release_id=111, tag_name="v1.0.0", html_url="https://github.com/org/repo/releases/v1.0.0"
        )
        assert "org/repo" in str(release)
        assert "v1.0.0" in str(release)

    def test_state_choices(self):
        assert GitHubRelease.ReleaseState.DRAFT == "draft"
        assert GitHubRelease.ReleaseState.PUBLISHED == "published"
        assert GitHubRelease.ReleaseState.PRERELEASE == "prerelease"

    def test_defaults(self, user):
        inst = GitHubInstallation.objects.create(
            user=user, installation_id=12345, account_login="testorg"
        )
        repo = GitHubRepo.objects.create(
            installation=inst, repo_id=67890, full_name="org/repo", name="repo", owner="org"
        )
        release = GitHubRelease.objects.create(
            repo=repo, release_id=111, tag_name="v1.0.0", html_url="https://github.com/org/repo/releases/v1.0.0"
        )
        assert release.state == "published"
        assert release.is_prerelease is False
        assert release.name == ""
        assert release.body == ""
        assert release.author == ""


@pytest.mark.django_db
class TestGitHubCheckRun:
    def test_str(self, user):
        inst = GitHubInstallation.objects.create(
            user=user, installation_id=12345, account_login="testorg"
        )
        repo = GitHubRepo.objects.create(
            installation=inst, repo_id=67890, full_name="org/repo", name="repo", owner="org"
        )
        check = GitHubCheckRun.objects.create(
            repo=repo, check_id=222, name="CI"
        )
        assert "CI" in str(check)
        assert "queued" in str(check)

    def test_status_choices(self):
        assert GitHubCheckRun.CheckStatus.QUEUED == "queued"
        assert GitHubCheckRun.CheckStatus.IN_PROGRESS == "in_progress"
        assert GitHubCheckRun.CheckStatus.COMPLETED == "completed"

    def test_conclusion_choices(self):
        assert GitHubCheckRun.CheckConclusion.SUCCESS == "success"
        assert GitHubCheckRun.CheckConclusion.FAILURE == "failure"
        assert GitHubCheckRun.CheckConclusion.NEUTRAL == "neutral"
        assert GitHubCheckRun.CheckConclusion.CANCELLED == "cancelled"
        assert GitHubCheckRun.CheckConclusion.SKIPPED == "skipped"
        assert GitHubCheckRun.CheckConclusion.TIMED_OUT == "timed_out"

    def test_defaults(self, user):
        inst = GitHubInstallation.objects.create(
            user=user, installation_id=12345, account_login="testorg"
        )
        repo = GitHubRepo.objects.create(
            installation=inst, repo_id=67890, full_name="org/repo", name="repo", owner="org"
        )
        check = GitHubCheckRun.objects.create(
            repo=repo, check_id=222, name="CI"
        )
        assert check.status == "queued"
        assert check.conclusion == ""
        assert check.html_url == ""
        assert check.started_at is None
        assert check.completed_at is None
        assert check.commit_sha == ""
        assert check.pull_request is None
