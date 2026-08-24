"""Servicio para enviar mensajes a Slack y Discord."""
import json
import requests
import logging
from django.utils import timezone

from .models import ChatIntegration, ChatMessageLog

logger = logging.getLogger(__name__)


def send_slack_message(webhook_url, text, blocks=None):
    """Envía un mensaje a Slack via webhook."""
    payload = {"text": text}
    if blocks:
        payload["blocks"] = blocks
    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        return resp.status_code == 200, resp.status_code, resp.text
    except Exception as e:
        return False, None, str(e)


def send_discord_message(webhook_url, content, embeds=None):
    """Envía un mensaje a Discord via webhook."""
    payload = {"content": content}
    if embeds:
        payload["embeds"] = embeds
    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        return resp.status_code in (200, 204), resp.status_code, resp.text
    except Exception as e:
        return False, None, str(e)


def notify_event(user, event, title, body, task=None):
    """Notifica un evento a todas las integraciones activas del usuario."""
    integrations = ChatIntegration.objects.filter(
        owner=user, is_active=True,
        events__contains=[event],
    )
    for integration in integrations:
        if integration.provider == ChatIntegration.Provider.SLACK:
            blocks = [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*{title}*\n{body}"},
                }
            ]
            if task:
                blocks.append({
                    "type": "context",
                    "elements": [{"type": "mrkdwn", "text": f"Task: {task.title}"}],
                })
            success, status_code, error = send_slack_message(
                integration.webhook_url, f"{title}: {body}", blocks
            )
        else:  # Discord
            embeds = [{
                "title": title,
                "description": body,
                "color": 25700,  # Azul
            }]
            if task:
                embeds[0]["fields"] = [{"name": "Task", "value": task.title}]
            success, status_code, error = send_discord_message(
                integration.webhook_url, f"**{title}**\n{body}", embeds
            )

        ChatMessageLog.objects.create(
            integration=integration,
            event=event,
            payload={"title": title, "body": body},
            status_code=status_code,
            success=success,
            error=error[:500] if error else "",
        )
