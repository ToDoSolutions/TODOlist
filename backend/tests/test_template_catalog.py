"""Catálogo comunitario de plantillas de proyecto."""
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.projects.models import Project, ProjectTemplate

pytestmark = pytest.mark.django_db
User = get_user_model()
URL = "/api/project-templates/"


@pytest.fixture
def owner(db):
    return User.objects.create_user(email="o@t.dev", username="o", password="x" * 20)


@pytest.fixture
def other(db):
    return User.objects.create_user(email="n@t.dev", username="n", password="x" * 20)


def _auth(u):
    c = APIClient()
    c.force_authenticate(user=u)
    return c


def _tpl(owner, **kw):
    kw.setdefault("name", "Tpl")
    kw.setdefault("config", {"tasks": [{"title": "T1"}]})
    return ProjectTemplate.objects.create(owner=owner, **kw)


class TestVisibility:
    def test_public_visible_to_everyone(self, owner, other):
        t = _tpl(owner, is_public=True)
        ids = [x["id"] for x in _auth(other).get(URL).json()]
        assert t.id in ids

    def test_private_not_visible(self, owner, other):
        t = _tpl(owner)
        ids = [x["id"] for x in _auth(other).get(URL).json()]
        assert t.id not in ids

    def test_community_filter(self, owner, other):
        pub = _tpl(owner, is_public=True)
        _tpl(owner)  # privada
        data = _auth(other).get(f"{URL}?community=true").json()
        assert [x["id"] for x in data] == [pub.id]

    def test_community_sorted_by_use(self, owner, other):
        a = _tpl(owner, name="A", is_public=True, use_count=5)
        b = _tpl(owner, name="B", is_public=True, use_count=50)
        data = _auth(other).get(f"{URL}?community=true").json()
        assert [x["id"] for x in data] == [b.id, a.id]


class TestPublishing:
    def test_owner_publishes(self, owner):
        t = _tpl(owner)
        r = _auth(owner).patch(f"{URL}{t.id}/", {"is_public": True})
        assert r.status_code == 200
        t.refresh_from_db()
        assert t.is_public

    def test_other_cannot_publish_or_edit(self, owner, other):
        t = _tpl(owner, is_public=True)
        r = _auth(other).patch(
            f"{URL}{t.id}/", {"is_public": False, "name": "hack"}
        )
        assert r.status_code in (403, 404)
        t.refresh_from_db()
        assert t.is_public and t.name == "Tpl"

    def test_other_cannot_delete(self, owner, other):
        t = _tpl(owner, is_public=True)
        assert _auth(other).delete(f"{URL}{t.id}/").status_code == 404

    def test_from_project_can_publish(self, owner, other):
        p = Project.objects.create(owner=owner, name="P")
        r = _auth(owner).post(
            f"{URL}from_project/",
            {"project_id": p.id, "name": "DesdeP", "public": True},
            format="json",
        )
        assert r.status_code == 201
        assert r.json()["is_public"] is True
        assert r.json()["author"] == "o"


class TestApply:
    def test_apply_increments_use_count(self, owner, other):
        t = _tpl(owner, is_public=True)
        r = _auth(other).post(
            f"{URL}{t.id}/apply/", {"name": "Mi proyecto"}, format="json"
        )
        assert r.status_code == 201
        t.refresh_from_db()
        assert t.use_count == 1
