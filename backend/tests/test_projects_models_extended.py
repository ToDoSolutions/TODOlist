"""Tests exhaustivos para modelos de projects."""
import pytest
from django.contrib.auth import get_user_model

from apps.projects.models import Project

User = get_user_model()


@pytest.mark.django_db
class TestProject:
    @pytest.fixture(autouse=True)
    def setup_data(self, db):
        self.user = User.objects.create_user(username="pm", email="pm@pm.com", password="pass")

    def test_str(self):
        p = Project.objects.create(owner=self.user, name="Test Project")
        assert str(p) == "Test Project"

    def test_defaults(self):
        p = Project.objects.create(owner=self.user, name="Test Project")
        assert p.description == ""
        assert p.color == "#1976d2"
        assert p.is_archived is False

    def test_ordering(self):
        p1 = Project.objects.create(owner=self.user, name="P1")
        p2 = Project.objects.create(owner=self.user, name="P2")
        from django.utils import timezone as _tz
        Project.objects.filter(pk=p1.pk).update(created_at=_tz.now() - _tz.timedelta(hours=1))
        projects = list(Project.objects.all())
        assert projects[0] == p2  # ordering by -created_at
