"""Tests exhaustivos para modelos de collaboration (parte 2)."""
import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

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


@pytest.fixture
def user(db):
    return User.objects.create_user(username="cm", email="cm@cm.com", password="pass")


@pytest.fixture
def user2(db):
    return User.objects.create_user(username="cm2", email="cm2@cm.com", password="pass")


@pytest.fixture
def project(user, db):
    return Project.objects.create(owner=user, name="Test Project")


@pytest.mark.django_db
class TestTeam:
    def test_str(self, user):
        team = Team.objects.create(name="Team 1", owner=user)
        assert "Team 1" in str(team)

    def test_defaults(self, user):
        team = Team.objects.create(name="Team 1", owner=user)
        assert team.description == ""
        assert not team.avatar


@pytest.mark.django_db
class TestTeamMembership:
    def test_str(self, user, user2):
        team = Team.objects.create(name="Team 1", owner=user)
        tm = TeamMembership.objects.create(team=team, user=user2, role="member")
        assert "Team 1" in str(tm)
        assert "cm2" in str(tm) or "member" in str(tm)

    def test_defaults(self, user, user2):
        team = Team.objects.create(name="Team 1", owner=user)
        tm = TeamMembership.objects.create(team=team, user=user2, role="member")
        assert tm.role == "member"

    def test_unique_together(self, user, user2):
        team = Team.objects.create(name="Team 1", owner=user)
        TeamMembership.objects.create(team=team, user=user2, role="member")
        with pytest.raises(IntegrityError):
            TeamMembership.objects.create(team=team, user=user2, role="admin")


@pytest.mark.django_db
class TestProjectMember:
    def test_str(self, user, project):
        pm = ProjectMember.objects.create(project=project, user=user, role="member")
        assert "Test Project" in str(pm)
        assert "cm" in str(pm) or "member" in str(pm)

    def test_defaults(self, user, project):
        pm = ProjectMember.objects.create(project=project, user=user, role="member")
        assert pm.role == "member"

    def test_unique_together(self, user, project):
        ProjectMember.objects.create(project=project, user=user, role="member")
        with pytest.raises(IntegrityError):
            ProjectMember.objects.create(project=project, user=user, role="admin")


@pytest.mark.django_db
class TestInvitation:
    def test_str(self, user, project):
        inv = Invitation.objects.create(
            target_type="project", target_id=project.id, invited_by=user,
            email="test@test.com", role="member", token="tok123"
        )
        assert "test@test.com" in str(inv)
        assert "project" in str(inv)

    def test_defaults(self, user, project):
        inv = Invitation.objects.create(
            target_type="project", target_id=project.id, invited_by=user,
            email="test@test.com", role="member", token="tok123"
        )
        assert inv.status == "pending"
        assert inv.expires_at is None
        assert inv.responded_at is None


@pytest.mark.django_db
class TestMention:
    def test_str(self, user, user2, project):
        task = Task.objects.create(owner=user, project=project, title="Task 1")
        comment = Comment.objects.create(task=task, author=user, body="Hello @cm2")
        mention = Mention.objects.create(
            comment=comment, task=task, mentioned_user=user2, mentioned_by=user
        )
        assert "cm2" in str(mention) or "Task 1" in str(mention)


@pytest.mark.django_db
class TestAuditLog:
    def test_str(self, user):
        log = AuditLog.objects.create(
            actor=user, action="login", resource_type="user", resource_id=user.id
        )
        assert "login" in str(log) or "user" in str(log)

    def test_action_choices(self):
        assert AuditLog.Action.LOGIN == "login"
        assert AuditLog.Action.LOGOUT == "logout"
        assert AuditLog.Action.LOGIN_FAILED == "login_failed"
        assert AuditLog.Action.CREATE == "create"
        assert AuditLog.Action.UPDATE == "update"
        assert AuditLog.Action.DELETE == "delete"
        assert AuditLog.Action.ROLE_CHANGE == "role_change"
