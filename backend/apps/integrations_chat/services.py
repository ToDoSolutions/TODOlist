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
