"""Handlers de eventos de dominio (efectos externos, fallibles).

Registrados en EventsConfig.ready(). Cada handler debe ser idempotente:
puede reintentarse tras un fallo.
"""
import hashlib
import hmac
import json
import logging

import requests
from django.utils import timezone

from .bus import register_handler

logger = logging.getLogger(__name__)


def _push_to_users(user_ids, group_suffix, event):
    """Push WebSocket a grupos user_{id}_{suffix} (misma convención actual)."""
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer

        layer = get_channel_layer()
        if not layer:
            return
        for uid in user_ids:
            async_to_sync(layer.group_send)(f"user_{uid}_{group_suffix}", event)
    except Exception:  # noqa: BLE001  # boundary intencional: fallo externo no rompe el flujo
        # Sin channel layer (tests, Redis caído): no romper el flujo
        logger.debug("WS push no disponible")


def _deliver_webhook(webhook, event_type, payload):
    """Entrega un webhook saliente: HMAC + SSRF guard + sin redirects."""
    from apps.integrations_chat.services import _is_safe_url
    if not _is_safe_url(webhook.url):
        logger.warning("Webhook %s con URL insegura, omitido", webhook.id)
        return
    body = json.dumps({
        "event": event_type,
        "timestamp": timezone.now().isoformat(),
        "data": payload,
    }).encode()
    headers = {"Content-Type": "application/json"}
    if webhook.secret:
        headers["X-Hub-Signature-256"] = "sha256=" + hmac.new(
            webhook.secret.encode(), body, hashlib.sha256
        ).hexdigest()
    requests.post(
        webhook.url, data=body, headers=headers,
        timeout=10, allow_redirects=False,
    )


_EVENT_MAP = {
    "task.created": "task_created",
    "task.updated": "task_updated",
    "task.deleted": "task_deleted",
}


@register_handler("task.created")
@register_handler("task.updated")
@register_handler("task.deleted")
def handle_task_event(event):
    """WS push a usuarios afectados + entrega de webhooks salientes."""
    payload = event.payload
    user_ids = payload.get("recipient_ids", [])

    # 1) Push WebSocket
    _push_to_users(user_ids, "tasks", payload.get("ws_event", {}))

    # 2) Webhooks salientes suscritos al evento
    wh_event = _EVENT_MAP.get(event.event_type)
    if wh_event:
        from apps.tasks.models import OutgoingWebhook
        for wh in OutgoingWebhook.objects.filter(
            owner_id=payload.get("owner_id"),
            is_active=True,
        ):
            if wh_event in (wh.events or []):
                _deliver_webhook(wh, wh_event, payload.get("task", {}))
