"""Videoconferencia Jitsi integrada en reuniones (Meeting.video_room).

POST /api/meetings/{id}/video/       → crea sala idempotente {room, url}
POST /api/meetings/{id}/close_video/ → cierra la sala (limpia video_room)
El serializer expone video_room (writable) y video_url (read-only).
"""
import pytest
from django.utils import timezone

from apps.collaboration.models import Meeting


def _meeting(user, **kwargs):
    return Meeting.objects.create(
        owner=user,
        title="Daily",
        scheduled_at=timezone.now(),
        **kwargs,
    )


@pytest.mark.django_db
class TestMeetingVideo:
    def test_video_crea_sala_y_persiste(self, authed_client, user):
        m = _meeting(user)
        resp = authed_client.post(f"/api/meetings/{m.id}/video/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["room"].startswith(f"todolist-m{m.id}-")
        assert data["url"] == f"https://meet.jit.si/{data['room']}"
        m.refresh_from_db()
        assert m.video_room == data["room"]

    def test_video_idempotente(self, authed_client, user):
        m = _meeting(user)
        r1 = authed_client.post(f"/api/meetings/{m.id}/video/")
        r2 = authed_client.post(f"/api/meetings/{m.id}/video/")
        assert r1.status_code == r2.status_code == 200
        assert r1.json() == r2.json()
        m.refresh_from_db()
        assert m.video_room == r1.json()["room"]

    def test_video_url_en_serializer(self, authed_client, user):
        m = _meeting(user)
        detail = authed_client.get(f"/api/meetings/{m.id}/").json()
        assert detail["video_room"] == ""
        assert detail["video_url"] is None

        authed_client.post(f"/api/meetings/{m.id}/video/")
        detail = authed_client.get(f"/api/meetings/{m.id}/").json()
        assert detail["video_room"].startswith(f"todolist-m{m.id}-")
        assert (
            detail["video_url"]
            == f"https://meet.jit.si/{detail['video_room']}"
        )

    def test_video_room_slug_custom_writable(self, authed_client, user):
        """video_room es writable: permite un slug custom vía PATCH."""
        m = _meeting(user)
        resp = authed_client.patch(
            f"/api/meetings/{m.id}/", {"video_room": "mi-sala-custom"}
        )
        assert resp.status_code == 200
        assert resp.json()["video_room"] == "mi-sala-custom"
        assert resp.json()["video_url"] == "https://meet.jit.si/mi-sala-custom"
        # video/ no pisa un slug custom ya existente (idempotente)
        data = authed_client.post(f"/api/meetings/{m.id}/video/").json()
        assert data["room"] == "mi-sala-custom"

    def test_close_video_limpia_sala(self, authed_client, user):
        m = _meeting(user)
        authed_client.post(f"/api/meetings/{m.id}/video/")
        resp = authed_client.post(f"/api/meetings/{m.id}/close_video/")
        assert resp.status_code == 200
        assert resp.json() == {"room": "", "url": None}
        m.refresh_from_db()
        assert m.video_room == ""
        detail = authed_client.get(f"/api/meetings/{m.id}/").json()
        assert detail["video_url"] is None

    def test_otro_usuario_404(self, authed_client_other, user):
        m = _meeting(user)
        assert (
            authed_client_other.post(f"/api/meetings/{m.id}/video/").status_code
            == 404
        )
        assert (
            authed_client_other.post(
                f"/api/meetings/{m.id}/close_video/"
            ).status_code
            == 404
        )
        m.refresh_from_db()
        assert m.video_room == ""

    def test_attendee_solo_lectura_403(self, authed_client_other, user, other_user):
        """Un attendee ve la reunión pero no puede gestionar el video."""
        m = _meeting(user)
        m.attendees.add(other_user)
        assert authed_client_other.get(f"/api/meetings/{m.id}/").status_code == 200
        assert (
            authed_client_other.post(f"/api/meetings/{m.id}/video/").status_code
            == 403
        )
        assert (
            authed_client_other.post(
                f"/api/meetings/{m.id}/close_video/"
            ).status_code
            == 403
        )

    def test_jitsi_base_url_override(self, authed_client, user, settings):
        """JITSI_BASE_URL es configurable (self-hosting) y sin barra final."""
        settings.JITSI_BASE_URL = "https://jitsi.example.com/"
        m = _meeting(user)
        data = authed_client.post(f"/api/meetings/{m.id}/video/").json()
        assert data["url"] == f"https://jitsi.example.com/{data['room']}"
        detail = authed_client.get(f"/api/meetings/{m.id}/").json()
        assert detail["video_url"] == f"https://jitsi.example.com/{data['room']}"

    def test_video_requiere_auth(self, api_client, user):
        m = _meeting(user)
        assert api_client.post(f"/api/meetings/{m.id}/video/").status_code == 401
