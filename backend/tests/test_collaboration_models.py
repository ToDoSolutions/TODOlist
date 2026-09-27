import pytest
from django.contrib.auth import get_user_model

from apps.collaboration.models import (
    AuditLog,
    Invitation,
    Mention,
    ProjectMember,
    Team,
    TeamMembership,
)
from apps.projects.models import Project
from apps.tasks.models import Comment, Task

User = get_user_model()


@pytest.mark.django_db
class TestTeam:
    @pytest.fixture(autouse=True)
    def setup_data(self, db):
        self.user = User.objects.create_user(username="cm", email="cm@cm.com", password="pass")

    def test_str(self):
        team = Team.objects.create(name="Team1", slug="team1", owner=self.user)
        assert str(team) == "Team1"

    def test_defaults(self):
        team = Team.objects.create(name="Team1", slug="team1", owner=self.user)
        assert team.description == ""


@pytest.mark.django_db
class TestTeamMembership:
    @pytest.fixture(autouse=True)
    def setup_data(self, db):
        self.user = User.objects.create_user(username="cm2", email="cm2@cm.com", password="pass")
        self.team = Team.objects.create(name="Team1", slug="team1", owner=self.user)

    def test_str(self):
        m = TeamMembership.objects.create(team=self.team, user=self.user, role="admin")
        assert "cm2@cm.com" in str(m)
        assert "Team1" in str(m)
        assert "admin" in str(m)

    def test_choices(self):
        assert TeamMembership.Role.OWNER == "owner"
        assert TeamMembership.Role.ADMIN == "admin"
        assert TeamMembership.Role.MEMBER == "member"
        assert TeamMembership.Role.GUEST == "guest"

    def test_defaults(self):
        m = TeamMembership.objects.create(team=self.team, user=self.user)
        assert m.role == "member"


@pytest.mark.django_db
class TestProjectMember:
    @pytest.fixture(autouse=True)
    def setup_data(self, db):
        self.user = User.objects.create_user(username="cm3", email="cm3@cm.com", password="pass")
        self.project = Project.objects.create(name="P1", owner=self.user)

    def test_str(self):
        m = ProjectMember.objects.create(project=self.project, user=self.user, role="editor")
        assert "cm3@cm.com" in str(m)
        assert "P1" in str(m)
        assert "editor" in str(m)

    def test_choices(self):
        assert ProjectMember.Role.OWNER == "owner"
        assert ProjectMember.Role.EDITOR == "editor"
        assert ProjectMember.Role.VIEWER == "viewer"

    def test_can_edit(self):
        m = ProjectMember.objects.create(project=self.project, user=self.user, role="editor")
        assert m.can_edit is True
        m.role = "viewer"
        assert m.can_edit is False
        m.role = "owner"
        assert m.can_edit is True

    def test_can_delete(self):
        m = ProjectMember.objects.create(project=self.project, user=self.user, role="owner")
        assert m.can_delete is True
        m.role = "editor"
        assert m.can_delete is False


@pytest.mark.django_db
class TestInvitation:
    @pytest.fixture(autouse=True)
    def setup_data(self, db):
        self.user = User.objects.create_user(username="cm4", email="cm4@cm.com", password="pass")

    def test_str(self):
        inv = Invitation.objects.create(target_type="project", target_id=1, email="e@e.com", invited_by=self.user, token="t1")
        assert "e@e.com" in str(inv)
        assert "project" in str(inv)
        assert "1" in str(inv)

    def test_choices(self):
        assert Invitation.TargetType.TEAM == "team"
        assert Invitation.TargetType.PROJECT == "project"
        assert Invitation.Status.PENDING == "pending"
        assert Invitation.Status.ACCEPTED == "accepted"
        assert Invitation.Status.DECLINED == "declined"
        assert Invitation.Status.EXPIRED == "expired"

    def test_defaults(self):
        inv = Invitation.objects.create(target_type="project", target_id=1, email="e@e.com", invited_by=self.user, token="t1")
        assert inv.status == "pending"
        assert inv.role == "member"


@pytest.mark.django_db
class TestMention:
    @pytest.fixture(autouse=True)
    def setup_data(self, db):
        self.user = User.objects.create_user(username="cm5", email="cm5@cm.com", password="pass")
        self.other = User.objects.create_user(username="other", email="other@other.com", password="pass")
        self.task = Task.objects.create(owner=self.user, title="T")
        self.comment = Comment.objects.create(task=self.task, author=self.user, body="C")

    def test_str(self):
        m = Mention.objects.create(comment=self.comment, task=self.task, mentioned_user=self.other, mentioned_by=self.user)
        assert "cm5@cm.com" in str(m)
        assert "other@other.com" in str(m)


@pytest.mark.django_db
class TestAuditLog:
    @pytest.fixture(autouse=True)
    def setup_data(self, db):
        self.user = User.objects.create_user(username="cm6", email="cm6@cm.com", password="pass")

    def test_str(self):
        log = AuditLog.objects.create(actor=self.user, action="login", resource_type="user", resource_id=1)
        assert "cm6@cm.com" in str(log)
        assert "login" in str(log)
        assert "user" in str(log)

    def test_choices(self):
        assert AuditLog.Action.LOGIN == "login"
        assert AuditLog.Action.LOGOUT == "logout"
        assert AuditLog.Action.LOGIN_FAILED == "login_failed"
        assert AuditLog.Action.CREATE == "create"
        assert AuditLog.Action.UPDATE == "update"
        assert AuditLog.Action.DELETE == "delete"
        assert AuditLog.Action.PERMISSION_CHANGE == "permission_change"
        assert AuditLog.Action.ROLE_CHANGE == "role_change"
        assert AuditLog.Action.EXPORT == "export"
        assert AuditLog.Action.SETTINGS_CHANGE == "settings_change"

    def test_defaults(self):
        log = AuditLog.objects.create(actor=self.user, action="login", resource_type="user")
        assert log.old_values == {}
        assert log.new_values == {}
        assert log.resource_name == ""
