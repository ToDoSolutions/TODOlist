import pytest
from django.contrib.auth import get_user_model

from apps.collaboration.audit import (
    log_action,
    log_create,
    log_delete,
    log_login,
    log_login_failed,
    log_role_change,
    log_update,
)
from apps.collaboration.mentions import extract_mentions, process_mentions
from apps.collaboration.models import AuditLog, Mention
from apps.notifications.models import Notification
from apps.tasks.models import Comment, Task

User = get_user_model()


@pytest.mark.django_db
class TestAuditLog:
    @pytest.fixture(autouse=True)
    def setup_data(self, db):
        self.user = User.objects.create_user(username="a1", email="a1@a.com", password="pass")

    def test_log_action(self):
        log = log_action(actor=self.user, action="create", resource_type="task", resource_id=1, resource_name="T", new_values={"title": "T"})
        assert log.action == "create"
        assert log.actor == self.user
        assert log.resource_name == "T"
        assert log.new_values == {"title": "T"}

    def test_log_action_defaults(self):
        log = log_action()
        assert log.action == "update"
        assert log.old_values == {}
        assert log.new_values == {}

    def test_log_login(self):
        log_login(self.user, ip_address="1.2.3.4", user_agent="Mozilla")
        log = AuditLog.objects.get(action="login")
        assert log.actor == self.user
        assert log.ip_address == "1.2.3.4"

    def test_log_login_failed(self):
        log_login_failed("a1@a.com", ip_address="1.2.3.4")
        log = AuditLog.objects.get(action="login_failed")
        assert log.actor == self.user
        assert log.resource_name == "a1@a.com"

    def test_log_create(self):
        log_create(self.user, "task", 1, "T", {"title": "T"})
        log = AuditLog.objects.get(action="create")
        assert log.new_values == {"title": "T"}

    def test_log_update(self):
        log_update(self.user, "task", 1, "T", {"title": "Old"}, {"title": "New"})
        log = AuditLog.objects.get(action="update")
        assert log.old_values == {"title": "Old"}
        assert log.new_values == {"title": "New"}

    def test_log_delete(self):
        log_delete(self.user, "task", 1, "T", {"title": "T"})
        log = AuditLog.objects.get(action="delete")
        assert log.old_values == {"title": "T"}

    def test_log_role_change(self):
        log_role_change(self.user, self.user, "member", "admin", "project", 1)
        log = AuditLog.objects.get(action="role_change")
        assert log.old_values == {"role": "member"}
        assert log.new_values == {"role": "admin"}

    def test_log_action_user_agent_truncated(self):
        log = log_action(user_agent="x" * 600)
        assert len(log.user_agent) == 500


@pytest.mark.django_db
class TestMentions:
    @pytest.fixture(autouse=True)
    def setup_data(self, db):
        self.user = User.objects.create_user(username="m1", email="m1@m.com", password="pass")
        self.other = User.objects.create_user(username="m2", email="m2@m.com", password="pass")
        from apps.collaboration.models import ProjectMember
        from apps.projects.models import Project
        self.project = Project.objects.create(owner=self.user, name="P")
        ProjectMember.objects.create(project=self.project, user=self.other, role="viewer")
        self.task = Task.objects.create(owner=self.user, project=self.project, title="T")

    def test_extract_mentions(self):
        assert extract_mentions("Hola @m1 y @m2") == {"m1", "m2"}
        assert extract_mentions("Sin menciones") == set()
        assert extract_mentions("@m1.test") == {"m1.test"}

    def test_process_mentions(self):
        comment = Comment.objects.create(task=self.task, author=self.user, body="Hola @m2")
        mentioned = process_mentions("Hola @m2", comment=comment, task=self.task, mentioned_by=self.user)
        assert len(mentioned) == 1
        assert mentioned[0] == self.other
        assert Mention.objects.filter(comment=comment, mentioned_user=self.other).exists()
        assert Notification.objects.filter(recipient=self.other, type="mention").exists()

    def test_process_mentions_by_email(self):
        mentioned = process_mentions("Hola @m2@m.com", task=self.task, mentioned_by=self.user)
        assert len(mentioned) == 1
        assert mentioned[0] == self.other

    def test_process_mentions_self(self):
        mentioned = process_mentions("Hola @m1", task=self.task, mentioned_by=self.user)
        assert mentioned == []
        assert not Mention.objects.exists()

    def test_process_mentions_empty(self):
        assert process_mentions("") == []
        assert process_mentions(None) == []

    def test_process_mentions_not_found(self):
        mentioned = process_mentions("Hola @nonexistent", task=self.task, mentioned_by=self.user)
        assert mentioned == []
