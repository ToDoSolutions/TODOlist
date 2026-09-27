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
from apps.tasks.models import Task

User = get_user_model()


@pytest.mark.django_db
class TestWebhookDelivery:
    def test_str(self):
        d = WebhookDelivery.objects.create(delivery_id="d1", event_type="issues", action="opened", repo_full_name="a/b")
        assert "d1" in str(d)
        assert "issues" in str(d)
        assert "opened" in str(d)

    def test_is_dead(self):
        d = WebhookDelivery.objects.create(delivery_id="d1", event_type="issues", status="dead_letter")
        assert d.is_dead is True
        d.status = "pending"
        assert d.is_dead is False

    def test_can_retry(self):
        d = WebhookDelivery.objects.create(delivery_id="d1", event_type="issues", retry_count=0, max_retries=5)
        assert d.can_retry is True
        d.retry_count = 5
        assert d.can_retry is False
        d.retry_count = 0
        d.status = "dead_letter"
        assert d.can_retry is False


@pytest.mark.django_db
class TestGitHubModels:
    @pytest.fixture(autouse=True)
    def setup_data(self, db):
        self.user = User.objects.create_user(username="im", email="im@im.com", password="pass")
        self.inst = GitHubInstallation.objects.create(user=self.user, installation_id=1, account_login="user")
        self.repo = GitHubRepo.objects.create(installation=self.inst, repo_id=1, full_name="a/b", name="b", owner="a")

    def test_installation_str(self):
        assert "user" in str(self.inst)
        assert "1" in str(self.inst)

    def test_repo_str(self):
        assert str(self.repo) == "a/b"

    def test_issue_link_str(self):
        task = Task.objects.create(owner=self.user, title="T")
        link = GitHubIssueLink.objects.create(task=task, repo=self.repo, issue_number=1, issue_id=100)
        assert "a/b#1" in str(link)
        assert "T" in str(link)

    def test_pull_request_str(self):
        pr = GitHubPullRequest.objects.create(repo=self.repo, pr_number=1, pr_id=100, title="PR", state="open")
        assert "a/b#1" in str(pr)
        assert "open" in str(pr)

    def test_commit_str(self):
        c = GitHubCommit.objects.create(repo=self.repo, sha="abc123456789", message="msg")
        assert "abc12345" in str(c)
        assert "a/b" in str(c)

    def test_release_str(self):
        r = GitHubRelease.objects.create(repo=self.repo, release_id=1, tag_name="v1.0")
        assert "a/b" in str(r)
        assert "v1.0" in str(r)

    def test_check_run_str(self):
        cr = GitHubCheckRun.objects.create(repo=self.repo, check_id=1, name="CI", status="completed", conclusion="success")
        assert "CI" in str(cr)
        assert "completed" in str(cr)
        assert "success" in str(cr)

    def test_check_run_str_no_conclusion(self):
        cr = GitHubCheckRun.objects.create(repo=self.repo, check_id=1, name="CI", status="in_progress")
        assert "—" in str(cr)

    def test_unique_together(self):
        with pytest.raises(IntegrityError):
            GitHubRepo.objects.create(installation=self.inst, repo_id=1, full_name="a/b", name="b", owner="a")

    def test_ordering(self):
        GitHubRepo.objects.create(installation=self.inst, repo_id=2, full_name="b/b", name="b", owner="b")
        r2 = GitHubRepo.objects.create(installation=self.inst, repo_id=3, full_name="a/a", name="a", owner="a")
        repos = list(GitHubRepo.objects.all())
        assert repos[0] == r2  # ordering by full_name
