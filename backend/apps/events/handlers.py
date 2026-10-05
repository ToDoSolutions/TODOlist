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
    resp = requests.post(
        webhook.url, data=body, headers=headers,
        timeout=10, allow_redirects=False,
    )
    # 4xx/5xx del receptor = entrega fallida → el evento queda FAILED y
    # process_pending_events lo reintenta (los handlers son idempotentes).
    resp.raise_for_status()


_EVENT_MAP = {
    "task.created": "task_created",
    "task.updated": "task_updated",
    "task.deleted": "task_deleted",
    "task.completed": "task_completed",
    "comment.created": "comment_added",
    "sprint.started": "sprint_started",
    "sprint.closed": "sprint_closed",
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
        _deliver_owner_webhooks(
            payload.get("owner_id"), wh_event, payload.get("task", {})
        )


@register_handler("task.completed")
@register_handler("comment.created")
@register_handler("sprint.started")
@register_handler("sprint.closed")
def handle_domain_webhook(event):
    """Webhooks salientes para eventos sin push WS propio
    (la completación ya viaja en task.updated; comentarios/sprints
    tienen sus propios canales de notificación)."""
    _deliver_owner_webhooks(
        event.payload.get("owner_id"),
        _EVENT_MAP[event.event_type],
        event.payload.get("data", {}),
    )


def _deliver_owner_webhooks(owner_id, wh_event, data):
    """Entrega a los OutgoingWebhook + ChatIntegration activos del
    owner suscritos al evento (misma lista de nombres de evento)."""
    if not owner_id:
        return
    from apps.tasks.models import OutgoingWebhook
    for wh in OutgoingWebhook.objects.filter(
        owner_id=owner_id, is_active=True
    ):
        if wh_event in (wh.events or []):
            _deliver_webhook(wh, wh_event, data)
    _deliver_chat_integrations(owner_id, wh_event, data)


_CHAT_LABELS = {
    "task_created": "Tarea creada",
    "task_updated": "Tarea actualizada",
    "task_completed": "Tarea completada",
    "task_deleted": "Tarea eliminada",
    "comment_added": "Nuevo comentario",
    "sprint_started": "Sprint iniciado",
    "sprint_closed": "Sprint cerrado",
}


def _chat_message(wh_event, data):
    """Texto plano del evento para Slack/Discord."""
    title = (
        data.get("title") or data.get("task_title") or data.get("name")
        or f"#{data.get('id', '?')}"
    )
    if wh_event == "comment_added":
        # data del comentario: enlazar a su tarea
        label = _CHAT_LABELS[wh_event]
        task_id = data.get("task_id")
    else:
        label = _CHAT_LABELS.get(wh_event, wh_event)
        task_id = data.get("id") if wh_event.startswith("task_") else None
    link = ""
    if task_id:
        link = f"/app/tasks?task={task_id}"
    elif wh_event.startswith("sprint_"):
        link = "/app/sprints"
    if link:
        from django.conf import settings
        base = getattr(settings, "DJANGO_FRONTEND_URL", "")
        link = f" <{base}{link}>"
    return f"[{label}] {title}{link}"


def _deliver_chat_integrations(owner_id, wh_event, data):
    """Slack/Discord del owner suscritos al evento + log de entrega."""
    try:
        from apps.integrations_chat.models import (
            ChatIntegration,
            ChatMessageLog,
        )
        from apps.integrations_chat.services import (
            send_discord_message,
            send_slack_message,
        )
        text = _chat_message(wh_event, data)
        for integ in ChatIntegration.objects.filter(
            owner_id=owner_id, is_active=True
        ):
            if wh_event not in (integ.events or []):
                continue
            if integ.provider == "slack":
                success, code, err = send_slack_message(
                    integ.webhook_url, text
                )
            else:
                success, code, err = send_discord_message(
                    integ.webhook_url, text
                )
            try:
                ChatMessageLog.objects.create(
                    integration=integ,
                    event=wh_event,
                    payload=data,
                    status_code=code,
                    success=success,
                    error=err or "",
                )
            except Exception:
                logger.exception("ChatMessageLog persist failed")
    except Exception:
        # Un fallo de chat no debe tumbar el handler completo
        logger.exception("Chat integration delivery failed")
