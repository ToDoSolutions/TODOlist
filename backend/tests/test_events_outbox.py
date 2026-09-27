"""Tests del outbox transaccional: publish, dispatch, reintentos, webhooks."""
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model

from apps.events.bus import process_pending_events, publish, register_handler
from apps.events.models import OutboxEvent
from apps.tasks.models import OutgoingWebhook, Task

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="ev", email="ev@e.com", password="p")


@pytest.mark.django_db
class TestOutbox:
    def test_publish_persiste_y_despacha(self):
        seen = []

        @register_handler("test.evt")
        def _h(ev):
            seen.append(ev.payload["x"])

        ev = publish("test.evt", {"x": 1})
        assert ev.status == OutboxEvent.Status.PROCESSED
        assert seen == [1]

    def test_handler_fallido_marca_failed(self):
        @register_handler("test.fail")
        def _h(ev):
            raise RuntimeError("boom")

        ev = publish("test.fail", {})
        assert ev.status == OutboxEvent.Status.FAILED
        assert "boom" in ev.last_error

    def test_reintento_procesa(self):
        calls = []

        @register_handler("test.retry")
        def _h(ev):
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("fallo temporal")

        ev = publish("test.retry", {})
        assert ev.status == OutboxEvent.Status.FAILED
        result = process_pending_events()
        ev.refresh_from_db()
        assert ev.status == OutboxEvent.Status.PROCESSED
        assert result["processed"] == 1

    def test_idempotency_dedup(self):
        ev1 = publish("test.dup", {}, idempotency_key="k1")
        ev2 = publish("test.dup", {}, idempotency_key="k1")
        assert ev1.id == ev2.id
        assert OutboxEvent.objects.filter(idempotency_key="k1").count() == 1

    def test_max_intentos_no_reintenta(self):
        ev = OutboxEvent.objects.create(
            event_type="test.none", status="failed", attempts=99
        )
        assert process_pending_events()["processed"] == 0
        ev.refresh_from_db()
        assert ev.attempts == 99


@pytest.mark.django_db
class TestTaskEvents:
    def test_save_publica_evento(self, user):
        task = Task.objects.create(owner=user, title="T")
        assert OutboxEvent.objects.filter(
            event_type="task.created",
            payload__task__id=task.id,
        ).exists()

    def test_update_publica_evento(self, user):
        task = Task.objects.create(owner=user, title="T")
        OutboxEvent.objects.all().delete()
        task.title = "T2"
        task.save()
        assert OutboxEvent.objects.filter(event_type="task.updated").exists()

    def test_delete_publica_evento(self, user):
        task = Task.objects.create(owner=user, title="T")
        tid = task.id
        task.delete()
        assert OutboxEvent.objects.filter(
            event_type="task.deleted",
            payload__task__id=tid,
        ).exists()

    def test_webhook_saliente_se_dispara(self, user):
        OutgoingWebhook.objects.create(
            owner=user, url="https://example.com/hook",
            events=["task_created"], secret="s3cr3t",
        )
        with patch("apps.events.handlers.requests") as mock_req, \
             patch("apps.integrations_chat.services._is_safe_url", return_value=True):
            Task.objects.create(owner=user, title="T")
            assert mock_req.post.called
            # HMAC presente
            headers = mock_req.post.call_args.kwargs["headers"]
            assert headers["X-Hub-Signature-256"].startswith("sha256=")

    def test_webhook_no_suscrito_no_dispara(self, user):
        OutgoingWebhook.objects.create(
            owner=user, url="https://example.com/hook",
            events=["task_deleted"],  # no suscrito a created
        )
        with patch("apps.events.handlers.requests") as mock_req, \
             patch("apps.integrations_chat.services._is_safe_url", return_value=True):
            Task.objects.create(owner=user, title="T")
            assert not mock_req.post.called

    def test_webhook_url_insegura_no_dispara(self, user):
        OutgoingWebhook.objects.create(
            owner=user, url="http://169.254.169.254/latest",
            events=["task_created"],
        )
        with patch("apps.events.handlers.requests") as mock_req:
            # SSRF check real (sin patch): IP de metadata debe bloquearse
            Task.objects.create(owner=user, title="T")
            assert not mock_req.post.called
