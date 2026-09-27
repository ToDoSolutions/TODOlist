"""Tests del orden manual de tareas (Task.position + POST /tasks/reorder/)."""
import pytest
from rest_framework.test import APIClient

from apps.tasks.models import Task
from apps.users.models import User


@pytest.fixture
def client_user(db):
    user = User.objects.create_user(
        email="reorder@example.com", username="reorder", password="x" * 20
    )
    client = APIClient()
    client.force_authenticate(user)
    return client, user


def _make(user, **kw):
    return Task.objects.create(owner=user, title=kw.pop("title", "t"), **kw)


@pytest.mark.django_db
class TestReorder:
    url = "/api/tasks/reorder/"

    def test_new_task_gets_incrementing_position(self, client_user):
        client, _ = client_user
        a = client.post("/api/tasks/", {"title": "a"}, format="json").json()
        b = client.post("/api/tasks/", {"title": "b"}, format="json").json()
        assert b["position"] > a["position"]

    def test_reorder_assigns_sequential_positions(self, client_user):
        client, user = client_user
        a = _make(user, title="a")
        b = _make(user, title="b")
        c = _make(user, title="c")
        res = client.post(self.url, {"task_ids": [c.id, a.id, b.id]}, format="json")
        assert res.status_code == 200
        assert res.json()["updated"] == 3
        assert list(
            Task.objects.order_by("position").values_list("id", flat=True)
        ) == [c.id, a.id, b.id]

    def test_reorder_visible_in_serializer_and_ordering(self, client_user):
        client, user = client_user
        a = _make(user, title="a")
        b = _make(user, title="b")
        client.post(self.url, {"task_ids": [b.id, a.id]}, format="json")
        res = client.get("/api/tasks/?ordering=position")
        payload = res.json()
        rows = payload["results"] if isinstance(payload, dict) else payload
        assert [t["title"] for t in rows] == ["b", "a"]
        assert "position" in rows[0]

    def test_reorder_foreign_task_404(self, client_user):
        client, user = client_user
        other = User.objects.create_user(
            email="other@example.com", username="other", password="x" * 20
        )
        foreign = _make(other, title="foreign")
        mine = _make(user, title="mine")
        res = client.post(
            self.url, {"task_ids": [mine.id, foreign.id]}, format="json"
        )
        assert res.status_code == 404

    def test_reorder_invalid_payload(self, client_user):
        client, _ = client_user
        assert client.post(self.url, {}, format="json").status_code == 400
        assert (
            client.post(
                self.url, {"task_ids": "not-a-list"}, format="json"
            ).status_code
            == 400
        )
