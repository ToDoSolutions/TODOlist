"""Tests del endpoint CalDAV (VTODO ↔ Task)."""
import base64

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from apps.caldav.ical import task_to_vtodo, uid_to_task_id, vtodo_to_fields
from apps.tasks.models import Task

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="cal@test.dev", username="cal", password="x" * 20,
        ical_token="tok-1234567890",
    )


def _basic(token):
    return "Basic " + base64.b64encode(f"u:{token}".encode()).decode()


def _req(method, path, token, **kw):
    c = Client()
    return c.generic(method, path, HTTP_AUTHORIZATION=_basic(token), **kw)


class TestAuth:
    def test_requires_token(self):
        assert Client().generic("PROPFIND", "/api/caldav/").status_code == 401

    def test_bad_token(self):
        r = _req("PROPFIND", "/api/caldav/", "wrong")
        assert r.status_code == 401

    def test_query_token(self, user):
        r = Client().generic("PROPFIND", "/api/caldav/?token=tok-1234567890")
        assert r.status_code == 207


class TestDiscovery:
    def test_options(self, user):
        r = _req("OPTIONS", "/api/caldav/", "tok-1234567890")
        assert r.status_code == 204
        assert "calendar-access" in r["DAV"]

    def test_principal(self, user):
        r = _req("PROPFIND", "/api/caldav/", "tok-1234567890")
        assert r.status_code == 207
        assert "calendar-home-set" in r.content.decode()
        assert "/api/caldav/tasks/" in r.content.decode()


class TestCollection:
    def test_propfind_lists_tasks(self, user):
        Task.objects.create(owner=user, title="Tarea A", position=1)
        r = _req("PROPFIND", "/api/caldav/tasks/", "tok-1234567890")
        body = r.content.decode()
        assert r.status_code == 207
        assert "task-1@todolist.ics" in body or "task-" in body

    def test_report_all(self, user):
        Task.objects.create(owner=user, title="Tarea B", position=1)
        r = _req(
            "REPORT", "/api/caldav/tasks/", "tok-1234567890",
            data="<calendar-query/>", content_type="application/xml",
        )
        body = r.content.decode()
        assert "Tarea B" in body
        assert "VTODO" in body


class TestObject:
    def test_get_put_delete_cycle(self, user):
        client = Client()
        hdrs = {"HTTP_AUTHORIZATION": _basic("tok-1234567890")}
        ics = (
            "BEGIN:VCALENDAR\r\nBEGIN:VTODO\r\n"
            "UID:client-abc-1\r\nSUMMARY:Comprar leche\r\n"
            "STATUS:NEEDS-ACTION\r\nPRIORITY:1\r\n"
            "DUE:20261201T090000Z\r\nEND:VTODO\r\nEND:VCALENDAR"
        )
        r = client.put("/api/caldav/tasks/client-abc-1.ics",
                       data=ics, content_type="text/calendar", **hdrs)
        assert r.status_code == 201
        t = Task.objects.get(owner=user, title="Comprar leche")
        assert t.priority == 0
        assert t.caldav_uid == "client-abc-1"

        r = client.get(f"/api/caldav/tasks/task-{t.id}@todolist.ics", **hdrs)
        assert r.status_code == 200
        assert "Comprar leche" in r.content.decode()

        r = client.generic(
            "DELETE", f"/api/caldav/tasks/task-{t.id}@todolist.ics", **hdrs
        )
        assert r.status_code == 204
        assert not Task.objects.filter(id=t.id).exists()

    def test_put_same_uid_updates(self, user):
        client = Client()
        hdrs = {"HTTP_AUTHORIZATION": _basic("tok-1234567890")}
        ics1 = ("BEGIN:VCALENDAR\r\nBEGIN:VTODO\r\nUID:u-9\r\n"
                "SUMMARY:Uno\r\nEND:VTODO\r\nEND:VCALENDAR")
        ics2 = ("BEGIN:VCALENDAR\r\nBEGIN:VTODO\r\nUID:u-9\r\n"
                "SUMMARY:Dos\r\nSTATUS:COMPLETED\r\nEND:VTODO\r\nEND:VCALENDAR")
        client.put("/api/caldav/tasks/u-9.ics", data=ics1,
                   content_type="text/calendar", **hdrs)
        client.put("/api/caldav/tasks/u-9.ics", data=ics2,
                   content_type="text/calendar", **hdrs)
        t = Task.objects.get(caldav_uid="u-9")
        assert t.title == "Dos"
        assert t.state == "completed"


class TestIcal:
    def test_roundtrip(self, user):
        task = Task.objects.create(
            owner=user, title="Reunión, A; B", description="line1\nline2",
            priority=1, position=1,
        )
        fields = vtodo_to_fields(task_to_vtodo(task))
        assert fields["title"] == "Reunión, A; B"
        assert fields["description"] == "line1\nline2"
        assert fields["priority"] == 1

    def test_uid_parse(self):
        assert uid_to_task_id("task-42@todolist") == 42
        assert uid_to_task_id("task-7.ics") == 7
        assert uid_to_task_id("random") is None
