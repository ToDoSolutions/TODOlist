"""Servicio para enviar mensajes a Slack y Discord."""
import ipaddress
import logging
import socket
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)


def _is_safe_url(url):
    """Valida que una URL no apunte a recursos internos (SSRF).

    Además de rechazar IPs literales privadas, resuelve el hostname por DNS
    y rechaza si TODAS sus IPs o cualquiera es privada/loopback/link-local/
    reservada (evita bypass por dominio que apunta a 127.0.0.1, etc.).
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme != "https":
            return False
        hostname = parsed.hostname or ""
        if hostname.lower() in ("localhost", "localhost.localdomain"):
            return False

        # IP literal
        try:
            ip = ipaddress.ip_address(hostname)
            ips = [ip]
        except ValueError:
            # Hostname: resolver DNS y validar cada IP resultante
            try:
                infos = socket.getaddrinfo(hostname, parsed.port or 443,
                                           proto=socket.IPPROTO_TCP)
                ips = [ipaddress.ip_address(i[4][0]) for i in infos]
            except socket.gaierror:
                return False
            if not ips:
                return False

        for ip in ips:
            if (ip.is_private or ip.is_loopback or ip.is_link_local
                    or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
                return False
        return True
    except Exception:  # noqa: BLE001  # boundary intencional: fallo externo no rompe el flujo
        return False


def send_slack_message(webhook_url, text, blocks=None):
    """Envía un mensaje a Slack via webhook."""
    payload = {"text": text}
    if blocks:
        payload["blocks"] = blocks
    if not _is_safe_url(webhook_url):
        return False, None, "URL not allowed"
    try:
        resp = requests.post(webhook_url, json=payload, timeout=10, allow_redirects=False)
        return resp.status_code == 200, resp.status_code, resp.text[:1000]
    except Exception as e:  # noqa: BLE001  # boundary intencional: fallo externo no rompe el flujo
        logger.warning("Slack webhook error: %s", type(e).__name__)
        return False, None, "Connection error"


def send_discord_message(webhook_url, content, embeds=None):
    """Envía un mensaje a Discord via webhook."""
    payload = {"content": content}
    if embeds:
        payload["embeds"] = embeds
    if not _is_safe_url(webhook_url):
        return False, None, "URL not allowed"
    try:
        resp = requests.post(webhook_url, json=payload, timeout=10, allow_redirects=False)
        return resp.status_code in (200, 204), resp.status_code, resp.text[:1000]
    except Exception as e:  # noqa: BLE001  # boundary intencional: fallo externo no rompe el flujo
        logger.warning("Discord webhook error: %s", type(e).__name__)
        return False, None, "Connection error"
