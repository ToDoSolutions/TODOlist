"""Tests para Web Push (VAPID): suscripciones, clave pública y envío."""
import json
from unittest.mock import Mock, patch

import pytest
from django.contrib.auth import get_user_model
from pywebpush import WebPushException

from apps.notifications.models import PushSubscription
from apps.notifications.services import notify

User = get_user_model()

ENDPOINT = "https://push.example.com/sub/abc123"
OTHER_ENDPOINT = "https://push.example.com/sub/xyz789"


def _sub(user, endpoint=ENDPOINT, p256dh="p256dh-key", auth="auth-secret"):
    return PushSubscription.objects.create(
        user=user, endpoint=endpoint, p256dh=p256dh, auth=auth
    )


@pytest.mark.django_db
class TestVapidKeyEndpoint:
    def test_returns_public_key(self, authed_client, settings):
        settings.VAPID_PUBLIC_KEY = "BPublicKeyTest123"
        resp = authed_client.get("/api/push/vapid-key/")
        assert resp.status_code == 200
        assert resp.json() == {"publicKey": "BPublicKeyTest123"}

    def test_404_when_unset(self, authed_client, settings):
        settings.VAPID_PUBLIC_KEY = ""
        resp = authed_client.get("/api/push/vapid-key/")
        assert resp.status_code == 404
        assert "detail" in resp.json()

    def test_requires_auth(self, api_client):
        assert api_client.get("/api/push/vapid-key/").status_code in (401, 403)


@pytest.mark.django_db
class TestPushSubscriptions:
    def test_create(self, authed_client, user):
        resp = authed_client.post(
            "/api/push/subscriptions/",
            {"endpoint": ENDPOINT, "keys": {"p256dh": "P256", "auth": "AUTH"}},
            format="json",
        )
        assert resp.status_code == 201
        sub = PushSubscription.objects.get()
        assert sub.user == user
        assert sub.endpoint == ENDPOINT
        assert sub.p256dh == "P256"
        assert sub.auth == "AUTH"

    def test_upsert_same_user_updates_keys(self, authed_client, user):
        _sub(user)
        resp = authed_client.post(
            "/api/push/subscriptions/",
            {
                "endpoint": ENDPOINT,
                "keys": {"p256dh": "NEW_P256", "auth": "NEW_AUTH"},
            },
            format="json",
        )
        assert resp.status_code == 200
        assert PushSubscription.objects.count() == 1
        sub = PushSubscription.objects.get()
        assert sub.p256dh == "NEW_P256"
        assert sub.auth == "NEW_AUTH"

    def test_endpoint_of_other_user_is_reassigned(
        self, authed_client, user, other_user
    ):
        """Si el endpoint existe para otro usuario se reasigna al actual."""
        _sub(other_user)
        resp = authed_client.post(
            "/api/push/subscriptions/",
            {
                "endpoint": ENDPOINT,
                "keys": {"p256dh": "NEW_P256", "auth": "NEW_AUTH"},
            },
            format="json",
        )
        assert resp.status_code == 200
        assert PushSubscription.objects.count() == 1
        sub = PushSubscription.objects.get(endpoint=ENDPOINT)
        assert sub.user == user  # reasignada
        assert sub.p256dh == "NEW_P256"

    def test_create_validates_payload(self, authed_client):
        resp = authed_client.post(
            "/api/push/subscriptions/", {"endpoint": ENDPOINT}, format="json"
        )
        assert resp.status_code == 400
        resp = authed_client.post(
            "/api/push/subscriptions/",
            {"keys": {"p256dh": "P", "auth": "A"}},
            format="json",
        )
        assert resp.status_code == 400
        assert not PushSubscription.objects.exists()

    def test_delete_own(self, authed_client, user):
        _sub(user)
        resp = authed_client.delete(
            "/api/push/subscriptions/", {"endpoint": ENDPOINT}, format="json"
        )
        assert resp.status_code == 204
        assert not PushSubscription.objects.exists()

    def test_delete_other_users_returns_404(self, authed_client, other_user):
        _sub(other_user)
        resp = authed_client.delete(
            "/api/push/subscriptions/", {"endpoint": ENDPOINT}, format="json"
        )
        assert resp.status_code == 404
        assert PushSubscription.objects.exists()

    def test_delete_requires_endpoint(self, authed_client):
        resp = authed_client.delete(
            "/api/push/subscriptions/", {}, format="json"
        )
        assert resp.status_code == 400

    def test_list_only_own(self, authed_client, user, other_user):
        _sub(user)
        _sub(other_user, endpoint=OTHER_ENDPOINT)
        resp = authed_client.get("/api/push/subscriptions/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["endpoint"] == ENDPOINT
        assert "created_at" in data[0]
        # Las claves de suscripción no se exponen en el listado
        assert "p256dh" not in data[0]
        assert "auth" not in data[0]

    def test_requires_auth(self, api_client):
        assert api_client.get("/api/push/subscriptions/").status_code in (
            401,
            403,
        )


@pytest.mark.django_db
class TestWebPushSend:
    def test_notify_calls_webpush(self, user, settings):
        settings.VAPID_PRIVATE_KEY = "priv-key"
        _sub(user)
        with patch("pywebpush.webpush") as mock_wp:
            notif = notify(
                user,
                "task_assigned",
                "Título",
                "Cuerpo",
                action_url="/app/tasks?task=1",
            )
        assert notif is not None
        mock_wp.assert_called_once()
        kwargs = mock_wp.call_args.kwargs
        assert kwargs["subscription_info"] == {
            "endpoint": ENDPOINT,
            "keys": {"p256dh": "p256dh-key", "auth": "auth-secret"},
        }
        assert kwargs["vapid_private_key"] == "priv-key"
        assert kwargs["vapid_claims"] == {"sub": "mailto:admin@todolist.local"}
        payload = json.loads(kwargs["data"])
        assert payload == {
            "title": "Título",
            "body": "Cuerpo",
            "url": "/app/tasks?task=1",
        }
        # last_used_at actualizado tras envío correcto
        assert PushSubscription.objects.get().last_used_at is not None

    def test_default_url_is_app(self, user, settings):
        settings.VAPID_PRIVATE_KEY = "priv-key"
        _sub(user)
        with patch("pywebpush.webpush") as mock_wp:
            notify(user, "custom", "T", "B")
        payload = json.loads(mock_wp.call_args.kwargs["data"])
        assert payload["url"] == "/app"

    def test_sends_to_each_subscription(self, user, settings):
        settings.VAPID_PRIVATE_KEY = "priv-key"
        _sub(user)
        _sub(user, endpoint=OTHER_ENDPOINT)
        with patch("pywebpush.webpush") as mock_wp:
            notify(user, "custom", "T", "B")
        assert mock_wp.call_count == 2
        endpoints = {
            c.kwargs["subscription_info"]["endpoint"]
            for c in mock_wp.call_args_list
        }
        assert endpoints == {ENDPOINT, OTHER_ENDPOINT}

    @pytest.mark.parametrize("code", [404, 410])
    def test_stale_endpoint_deleted_on_gone(self, user, settings, code):
        settings.VAPID_PRIVATE_KEY = "priv-key"
        sub = _sub(user)
        response = Mock()
        response.status_code = code
        with patch(
            "pywebpush.webpush",
            side_effect=WebPushException("Gone", response=response),
        ):
            notif = notify(user, "custom", "T", "B")
        assert notif is not None
        assert not PushSubscription.objects.filter(pk=sub.pk).exists()

    def test_other_error_keeps_subscription(self, user, settings):
        settings.VAPID_PRIVATE_KEY = "priv-key"
        sub = _sub(user)
        response = Mock()
        response.status_code = 500
        with patch(
            "pywebpush.webpush",
            side_effect=WebPushException("boom", response=response),
        ):
            notif = notify(user, "custom", "T", "B")
        assert notif is not None  # no rompe el flujo
        assert PushSubscription.objects.filter(pk=sub.pk).exists()

    def test_generic_exception_does_not_break_notify(self, user, settings):
        settings.VAPID_PRIVATE_KEY = "priv-key"
        _sub(user)
        with patch("pywebpush.webpush", side_effect=RuntimeError("net down")):
            notif = notify(user, "custom", "T", "B")
        assert notif is not None
        assert PushSubscription.objects.exists()

    def test_no_op_when_vapid_unset(self, user, settings):
        """Sin VAPID_PRIVATE_KEY el envío es no-op (no crash, no llamada)."""
        settings.VAPID_PRIVATE_KEY = ""
        _sub(user)
        with patch("pywebpush.webpush") as mock_wp:
            notif = notify(user, "custom", "T", "B")
        assert notif is not None
        mock_wp.assert_not_called()

    def test_no_subscriptions_no_call(self, user, settings):
        settings.VAPID_PRIVATE_KEY = "priv-key"
        with patch("pywebpush.webpush") as mock_wp:
            notify(user, "custom", "T", "B")
        mock_wp.assert_not_called()
