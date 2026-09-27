"""Tests exhaustivos para collaboration/signals.py."""
from unittest.mock import MagicMock

import pytest
from django.contrib.auth import get_user_model
from django.test import RequestFactory

from apps.collaboration.models import AuditLog
from apps.collaboration.signals import _get_client_ip
from apps.projects.models import Project
from apps.tasks.models import Comment, Task

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="cs", email="cs@cs.com", password="pass")


@pytest.fixture
def project(user, db):
    return Project.objects.create(owner=user, name="Test Project")


@pytest.mark.django_db
class TestGetClientIp:
    def test_remote_addr(self):
        factory = RequestFactory()
        request = factory.get("/")
        request.META["REMOTE_ADDR"] = "1.2.3.4"
        assert _get_client_ip(request) == "1.2.3.4"

    def test_x_forwarded_for_untrusted(self):
        """X-Forwarded-For no se confía si REMOTE_ADDR no es proxy confiable."""
        factory = RequestFactory()
        request = factory.get("/")
        request.META["REMOTE_ADDR"] = "1.2.3.4"
        request.META["HTTP_X_FORWARDED_FOR"] = "5.6.7.8"
        assert _get_client_ip(request) == "1.2.3.4"

    def test_x_forwarded_for_trusted(self):
        """X-Forwarded-For se usa si REMOTE_ADDR es proxy confiable."""
        from django.test import override_settings
        factory = RequestFactory()
        request = factory.get("/")
        request.META["REMOTE_ADDR"] = "10.0.0.1"
        request.META["HTTP_X_FORWARDED_FOR"] = "5.6.7.8, 9.10.11.12"
        with override_settings(TRUSTED_PROXY_IPS=["10.0.0.0/8"]):
            assert _get_client_ip(request) == "5.6.7.8"

    def test_invalid_remote_addr(self):
        from django.test import override_settings
        factory = RequestFactory()
        request = factory.get("/")
        request.META["REMOTE_ADDR"] = "invalid"
        request.META["HTTP_X_FORWARDED_FOR"] = "5.6.7.8"
        with override_settings(TRUSTED_PROXY_IPS=["10.0.0.0/8"]):
            assert _get_client_ip(request) == "invalid"


@pytest.mark.django_db
class TestMentionsSignal:
    def test_mention_created(self, user, project):
        """Verifica que se procesan menciones al crear comentario."""
        other = User.objects.create_user(username="mentioned", email="m@m.com", password="pass")
        task = Task.objects.create(owner=user, project=project, title="Task")
        from apps.collaboration.models import ProjectMember
        ProjectMember.objects.create(project=project, user=other, role="viewer")
        Comment.objects.create(task=task, author=user, body="Hey @mentioned check this")
        from apps.collaboration.models import Mention
        assert Mention.objects.filter(mentioned_user=other).exists()

    def test_no_mention_on_update(self, user, project):
        """Verifica que no procesa menciones en actualización."""
        task = Task.objects.create(owner=user, project=project, title="Task")
        comment = Comment.objects.create(task=task, author=user, body="Hello")
        comment.body = "@mentioned"
        comment.save()
        from apps.collaboration.models import Mention
        assert not Mention.objects.exists()


@pytest.mark.django_db
class TestAuditSignals:
    def test_login_logged(self, user):
        """Verifica que el login se registra en audit log."""
        from django.contrib.auth.signals import user_logged_in
        request = MagicMock()
        request.META = {"REMOTE_ADDR": "1.2.3.4", "HTTP_USER_AGENT": "Test"}
        user_logged_in.send(sender=User, request=request, user=user)
        assert AuditLog.objects.filter(actor=user, action="login").exists()

    def test_logout_logged(self, user):
        """Verifica que el logout se registra en audit log."""
        from django.contrib.auth.signals import user_logged_out
        request = MagicMock()
        request.META = {"REMOTE_ADDR": "1.2.3.4", "HTTP_USER_AGENT": "Test"}
        user_logged_out.send(sender=User, request=request, user=user)
        assert AuditLog.objects.filter(actor=user, action="logout").exists()

    def test_login_failed_logged(self):
        """Verifica que los logins fallidos se registran."""
        from django.contrib.auth.signals import user_login_failed
        request = MagicMock()
        request.META = {"REMOTE_ADDR": "1.2.3.4", "HTTP_USER_AGENT": "Test"}
        user_login_failed.send(
            sender=User, credentials={"email": "bad@bad.com"}, request=request
        )
        assert AuditLog.objects.filter(action="login_failed").exists()
