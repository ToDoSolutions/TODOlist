"""Tests del endpoint MCP (JSON-RPC sobre POST /api/mcp/)."""
import json

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.tasks.models import Task
from apps.users.models import APIKey

pytestmark = pytest.mark.django_db
User = get_user_model()
URL = "/api/mcp/"


def _rpc(method, params=None, req_id=1):
    return {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}}


def _post(client, payload):
    return client.post(URL, json.dumps(payload), content_type="application/json")


@pytest.fixture
def user():
    return User.objects.create_user(
        email="mcp@test.dev", password="x" * 20, username="mcp"
    )


@pytest.fixture
def client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


class TestProtocol:
    def test_requires_auth(self):
        assert _post(APIClient(), _rpc("initialize")).status_code in (401, 403)

    def test_initialize(self, client):
        r = _post(client, _rpc("initialize"))
        assert r.status_code == 200
        result = r.json()["result"]
        assert result["serverInfo"]["name"] == "todolist-mcp"
        assert "tools" in result["capabilities"]

    def test_notification_returns_202(self, client):
        r = _post(client, {"jsonrpc": "2.0", "method": "notifications/initialized"})
        assert r.status_code == 202

    def test_unknown_method(self, client):
        r = _post(client, _rpc("no/existe"))
        assert r.json()["error"]["code"] == -32601

    def test_batch(self, client):
        r = _post(client, [_rpc("ping", req_id=1), _rpc("tools/list", req_id=2)])
        assert len(r.json()) == 2


class TestTools:
    def test_tools_list(self, client):
        r = _post(client, _rpc("tools/list"))
        names = {t["name"] for t in r.json()["result"]["tools"]}
        assert {"tasks_list", "tasks_create", "tasks_complete"} <= names

    def test_create_and_list(self, client, user):
        r = _post(client, _rpc("tools/call", {
            "name": "tasks_create",
            "arguments": {"title": "Desde MCP", "priority": 1},
        }))
        body = r.json()["result"]
        assert body["isError"] is False
        created = json.loads(body["content"][0]["text"])
        assert Task.objects.get(id=created["id"]).owner == user

        r = _post(client, _rpc("tools/call", {
            "name": "tasks_list", "arguments": {"q": "MCP"},
        }))
        tasks = json.loads(r.json()["result"]["content"][0]["text"])["tasks"]
        assert any(t["title"] == "Desde MCP" for t in tasks)

    def test_complete(self, client, user):
        task = Task.objects.create(title="x", owner=user, position=1)
        r = _post(client, _rpc("tools/call", {
            "name": "tasks_complete", "arguments": {"id": task.id},
        }))
        assert r.json()["result"]["isError"] is False
        task.refresh_from_db()
        assert task.state == "completed"

    def test_comments_add(self, client, user):
        """Regresión: el campo del modelo es `body`, no `text`."""
        task = Task.objects.create(title="x", owner=user, position=1)
        r = _post(client, _rpc("tools/call", {
            "name": "comments_add",
            "arguments": {"task_id": task.id, "text": "hola mcp"},
        }))
        body = r.json()["result"]
        assert body["isError"] is False
        from apps.tasks.models import Comment
        c = Comment.objects.get(task=task)
        assert c.body == "hola mcp" and c.author == user

    def test_create_with_project_id(self, client, user):
        """Regresión: el schema expone project_id y debe mapearse a
        ``project`` (antes se descartaba silenciosamente)."""
        from apps.projects.models import Project

        p = Project.objects.create(owner=user, name="P1")
        r = _post(client, _rpc("tools/call", {
            "name": "tasks_create",
            "arguments": {"title": "Con proyecto", "project_id": p.id},
        }))
        body = r.json()["result"]
        assert body["isError"] is False
        created = json.loads(body["content"][0]["text"])
        assert Task.objects.get(id=created["id"]).project_id == p.id

    def test_update_with_project_id(self, client, user):
        from apps.projects.models import Project

        p = Project.objects.create(owner=user, name="P1")
        task = Task.objects.create(title="x", owner=user, position=1)
        r = _post(client, _rpc("tools/call", {
            "name": "tasks_update",
            "arguments": {"id": task.id, "project_id": p.id},
        }))
        assert r.json()["result"]["isError"] is False
        task.refresh_from_db()
        assert task.project_id == p.id

    def test_complete_inaccessible_task_errors_cleanly(self, client, user):
        """Una tarea inaccesible/no editable → isError, no crash."""
        other = User.objects.create_user(
            email="o2@test.dev", password="x" * 20, username="o2"
        )
        task = Task.objects.create(title="x", owner=other, position=1)
        r = _post(client, _rpc("tools/call", {
            "name": "tasks_complete", "arguments": {"id": task.id},
        }))
        assert r.json()["result"]["isError"] is True
        task.refresh_from_db()
        assert task.state != "completed"

    def test_comments_add_on_readonly_shared_task(self, client, user):
        """Paridad REST: comentar exige escritura sobre la tarea —
        un viewer del proyecto no puede comentar (403 REST ≡ isError MCP);
        un editor sí."""
        from apps.collaboration.models import ProjectMember
        from apps.projects.models import Project

        other = User.objects.create_user(
            email="o3@test.dev", password="x" * 20, username="o3"
        )
        p = Project.objects.create(owner=other, name="Shared")
        membership = ProjectMember.objects.create(
            project=p, user=user, role="viewer"
        )
        task = Task.objects.create(title="x", owner=other, project=p, position=1)
        r = _post(client, _rpc("tools/call", {
            "name": "comments_add",
            "arguments": {"task_id": task.id, "text": "solo lectura"},
        }))
        assert r.json()["result"]["isError"] is True

        membership.role = "editor"
        membership.save(update_fields=["role"])
        r = _post(client, _rpc("tools/call", {
            "name": "comments_add",
            "arguments": {"task_id": task.id, "text": "con escritura"},
        }))
        assert r.json()["result"]["isError"] is False

    def test_unknown_tool(self, client):
        r = _post(client, _rpc("tools/call", {"name": "nope"}))
        assert r.json()["result"]["isError"] is True

    def test_apikey_read_scope_cannot_write(self, user):
        raw, hashed, prefix = APIKey.generate_key()
        APIKey.objects.create(
            user=user, name="t", hashed_key=hashed,
            key_prefix=prefix, scopes=["read"],
        )
        c = APIClient()
        r = c.post(
            URL,
            json.dumps(_rpc("tools/call", {
                "name": "tasks_create", "arguments": {"title": "x"},
            })),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"ApiKey {raw}",
        )
        assert r.status_code == 200
        assert r.json()["result"]["isError"] is True
