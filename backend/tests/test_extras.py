"""Tests para features extra de collaboration:

- ExternalCalendar/ExternalEvent: CRUD owner-scoped, sync de feeds iCal
  (parsing de VEVENT con DATE vs DATETIME), endpoint de refresh y
  filtrado de eventos por rango.
- Whiteboard: CRUD por proyecto con acceso lectura/escritura.
"""
from datetime import UTC
from unittest.mock import Mock, patch

import pytest

from apps.collaboration.models import (
    ExternalCalendar,
    ExternalEvent,
    Whiteboard,
)

ICS_FEED = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
UID:evt-all-day-1
SUMMARY:All day event
DTSTART;VALUE=DATE:20250610
DTEND;VALUE=DATE:20250611
END:VEVENT
BEGIN:VEVENT
UID:evt-timed-1
SUMMARY:Timed event
DTSTART:20250615T100000Z
DTEND:20250615T110000Z
END:VEVENT
END:VCALENDAR
"""


def _mock_ics_response(content=ICS_FEED):
    resp = Mock()
    resp.content = content
    resp.raise_for_status = Mock()
    return resp


@pytest.mark.django_db
class TestExternalCalendarCRUD:
    def test_create_list(self, authed_client, user):
        resp = authed_client.post("/api/external-calendars/", {
            "name": "Google Cal",
            "url": "https://calendar.example.com/feed.ics",
            "color": "#ff0000",
        })
        assert resp.status_code == 201
        assert resp.data["name"] == "Google Cal"
        assert ExternalCalendar.objects.filter(user=user).count() == 1

        resp = authed_client.get("/api/external-calendars/")
        assert resp.status_code == 200
        assert len(resp.data) == 1

    def test_update_and_delete(self, authed_client, user):
        cal = ExternalCalendar.objects.create(
            user=user, name="Cal", url="https://example.com/x.ics",
        )
        resp = authed_client.patch(
            f"/api/external-calendars/{cal.id}/",
            {"name": "Renamed", "is_active": False},
            format="json",
        )
        assert resp.status_code == 200
        cal.refresh_from_db()
        assert cal.name == "Renamed"
        assert cal.is_active is False

        resp = authed_client.delete(f"/api/external-calendars/{cal.id}/")
        assert resp.status_code == 204
        assert not ExternalCalendar.objects.filter(pk=cal.pk).exists()

    def test_owner_scoped(self, authed_client_other, user):
        """Otro usuario no ve ni toca calendarios ajenos (404)."""
        cal = ExternalCalendar.objects.create(
            user=user, name="Privado", url="https://example.com/x.ics",
        )
        resp = authed_client_other.get("/api/external-calendars/")
        assert resp.status_code == 200
        assert resp.data == []
        for method in ("get", "patch", "delete"):
            resp = getattr(authed_client_other, method)(
                f"/api/external-calendars/{cal.id}/"
            )
            assert resp.status_code == 404

    def test_unauthenticated(self, api_client):
        resp = api_client.get("/api/external-calendars/")
        assert resp.status_code == 401


@pytest.mark.django_db
class TestExternalCalendarSync:
    def _sync(self, user, content=ICS_FEED):
        from apps.collaboration.tasks import sync_external_calendar

        cal = ExternalCalendar.objects.create(
            user=user, name="Feed", url="https://example.com/feed.ics",
        )
        with patch(
            "apps.collaboration.tasks._is_safe_url", return_value=True
        ), patch(
            "apps.collaboration.tasks.requests.get",
            return_value=_mock_ics_response(content),
        ):
            count = sync_external_calendar(cal)
        return cal, count

    def test_sync_parses_date_and_datetime(self, user):
        """DTSTART;VALUE=DATE → all_day=True; DTSTART datetime → all_day=False."""
        cal, count = self._sync(user)
        assert count == 2
        cal.refresh_from_db()
        assert cal.last_synced_at is not None
        assert cal.last_error == ""

        all_day = cal.events.get(uid="evt-all-day-1")
        assert all_day.all_day is True
        assert all_day.dtstart.hour == 0 and all_day.dtstart.minute == 0

        timed = cal.events.get(uid="evt-timed-1")
        assert timed.all_day is False
        assert timed.dtstart.hour == 10
        assert timed.dtend.hour == 11

    def test_sync_replaces_previous_events(self, user):
        from apps.collaboration.tasks import sync_external_calendar

        cal, _ = self._sync(user)
        cal.events.create(
            uid="stale", summary="viejo",
            dtstart="2025-01-01T00:00:00Z",
        )
        with patch(
            "apps.collaboration.tasks._is_safe_url", return_value=True
        ), patch(
            "apps.collaboration.tasks.requests.get",
            return_value=_mock_ics_response(),
        ):
            sync_external_calendar(cal)
        assert cal.events.count() == 2
        assert not cal.events.filter(uid="stale").exists()

    def test_sync_network_error_graceful(self, user):
        import requests as req

        from apps.collaboration.tasks import sync_external_calendar

        cal = ExternalCalendar.objects.create(
            user=user, name="Feed", url="https://example.com/feed.ics",
        )
        with patch(
            "apps.collaboration.tasks._is_safe_url", return_value=True
        ), patch(
            "apps.collaboration.tasks.requests.get",
            side_effect=req.ConnectionError("boom"),
        ):
            count = sync_external_calendar(cal)
        assert count is None
        cal.refresh_from_db()
        assert "Error de red" in cal.last_error
        assert cal.last_synced_at is None

    def test_sync_invalid_ical_graceful(self, user):
        cal, count = self._sync(user, content=b"NOT AN ICAL AT ALL{{{")
        assert count is None or count == 0
        cal.refresh_from_db()
        # parse error → last_error, o feed sin VEVENTs → 0 eventos
        assert cal.events.count() == 0

    def test_sync_unsafe_url_rejected(self, user):
        from apps.collaboration.tasks import sync_external_calendar

        cal = ExternalCalendar.objects.create(
            user=user, name="Feed", url="https://example.com/feed.ics",
        )
        with patch(
            "apps.collaboration.tasks._is_safe_url", return_value=False
        ), patch(
            "apps.collaboration.tasks.requests.get"
        ) as mock_get:
            count = sync_external_calendar(cal)
        assert count is None
        assert not mock_get.called
        cal.refresh_from_db()
        assert "URL no permitida" in cal.last_error

    def test_beat_task_syncs_active_only(self, user):
        from apps.collaboration.tasks import sync_external_calendars

        active = ExternalCalendar.objects.create(
            user=user, name="A", url="https://example.com/a.ics",
        )
        inactive = ExternalCalendar.objects.create(
            user=user, name="B", url="https://example.com/b.ics",
            is_active=False,
        )
        with patch(
            "apps.collaboration.tasks._is_safe_url", return_value=True
        ), patch(
            "apps.collaboration.tasks.requests.get",
            return_value=_mock_ics_response(),
        ) as mock_get:
            result = sync_external_calendars()
        assert "1" in result
        assert mock_get.call_count == 1
        active.refresh_from_db()
        assert active.events.count() == 2
        assert inactive.events.count() == 0

    def test_refresh_endpoint(self, authed_client, user):
        cal = ExternalCalendar.objects.create(
            user=user, name="Feed", url="https://example.com/feed.ics",
        )
        with patch(
            "apps.collaboration.tasks._is_safe_url", return_value=True
        ), patch(
            "apps.collaboration.tasks.requests.get",
            return_value=_mock_ics_response(),
        ):
            resp = authed_client.post(
                f"/api/external-calendars/{cal.id}/refresh/"
            )
        assert resp.status_code == 200
        assert resp.data["events_imported"] == 2
        assert resp.data["last_synced_at"] is not None
        assert cal.events.count() == 2

    def test_events_range_filter(self, authed_client, user):
        from datetime import datetime

        cal = ExternalCalendar.objects.create(
            user=user, name="Feed", url="https://example.com/feed.ics",
        )
        ExternalEvent.objects.create(
            calendar=cal, uid="in", summary="in range",
            dtstart=datetime(2025, 6, 15, 10, tzinfo=UTC),
            dtend=datetime(2025, 6, 15, 11, tzinfo=UTC),
        )
        ExternalEvent.objects.create(
            calendar=cal, uid="out", summary="out of range",
            dtstart=datetime(2025, 8, 1, 10, tzinfo=UTC),
        )
        url = f"/api/external-calendars/{cal.id}/events/"
        resp = authed_client.get(
            url, {"start": "2025-06-01", "end": "2025-06-30"}
        )
        assert resp.status_code == 200
        uids = [e["uid"] for e in resp.data]
        assert "in" in uids
        assert "out" not in uids

        # Sin filtros devuelve todos
        resp = authed_client.get(url)
        assert len(resp.data) == 2

    def test_events_owner_scoped(self, authed_client_other, user):
        cal = ExternalCalendar.objects.create(
            user=user, name="Feed", url="https://example.com/feed.ics",
        )
        resp = authed_client_other.get(
            f"/api/external-calendars/{cal.id}/events/"
        )
        assert resp.status_code == 404
        resp = authed_client_other.post(
            f"/api/external-calendars/{cal.id}/refresh/"
        )
        assert resp.status_code == 404


@pytest.mark.django_db
class TestWhiteboard:
    def test_create_and_list(self, authed_client, user, project):
        resp = authed_client.post("/api/whiteboards/", {
            "project": project.id,
            "name": "Board 1",
        }, format="json")
        assert resp.status_code == 201
        assert resp.data["content"] == {"nodes": [], "edges": []}
        assert resp.data["owner"] == user.id

        resp = authed_client.get("/api/whiteboards/")
        assert resp.status_code == 200
        assert len(resp.data) == 1

    def test_partial_content_update(self, authed_client, user, project):
        wb = Whiteboard.objects.create(
            project=project, owner=user, name="B",
        )
        content = {
            "nodes": [
                {"id": "n1", "x": 10, "y": 20, "text": "Hola",
                 "color": "#fff", "w": 100, "h": 50},
            ],
            "edges": [{"from": "n1", "to": "n2"}],
        }
        resp = authed_client.patch(
            f"/api/whiteboards/{wb.id}/",
            {"content": content},
            format="json",
        )
        assert resp.status_code == 200
        wb.refresh_from_db()
        assert wb.content == content

    def test_non_member_gets_404(self, authed_client_other, user, project):
        """Un usuario sin acceso al proyecto no ve la pizarra."""
        wb = Whiteboard.objects.create(
            project=project, owner=user, name="B",
        )
        resp = authed_client_other.get("/api/whiteboards/")
        assert resp.data == []
        resp = authed_client_other.get(f"/api/whiteboards/{wb.id}/")
        assert resp.status_code == 404
        resp = authed_client_other.patch(
            f"/api/whiteboards/{wb.id}/", {"name": "x"}, format="json"
        )
        assert resp.status_code == 404
        resp = authed_client_other.delete(f"/api/whiteboards/{wb.id}/")
        assert resp.status_code == 404

    def test_non_member_cannot_create_in_foreign_project(
        self, authed_client_other, project
    ):
        resp = authed_client_other.post("/api/whiteboards/", {
            "project": project.id, "name": "hack",
        }, format="json")
        assert resp.status_code == 403

    def test_viewer_can_read_but_not_write(
        self, authed_client_other, other_user, user, project
    ):
        from apps.collaboration.models import ProjectMember

        ProjectMember.objects.create(
            project=project, user=other_user,
            role=ProjectMember.Role.VIEWER,
        )
        wb = Whiteboard.objects.create(
            project=project, owner=user, name="B",
        )
        resp = authed_client_other.get(f"/api/whiteboards/{wb.id}/")
        assert resp.status_code == 200
        resp = authed_client_other.patch(
            f"/api/whiteboards/{wb.id}/", {"name": "x"}, format="json"
        )
        assert resp.status_code == 404

    def test_editor_can_write(
        self, authed_client_other, other_user, user, project
    ):
        from apps.collaboration.models import ProjectMember

        ProjectMember.objects.create(
            project=project, user=other_user,
            role=ProjectMember.Role.EDITOR,
        )
        wb = Whiteboard.objects.create(
            project=project, owner=user, name="B",
        )
        resp = authed_client_other.patch(
            f"/api/whiteboards/{wb.id}/", {"name": "editado"},
            format="json",
        )
        assert resp.status_code == 200
        wb.refresh_from_db()
        assert wb.name == "editado"
