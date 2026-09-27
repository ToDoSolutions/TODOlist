"""Tareas Celery de notificaciones: digest diario por email."""
import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from .models import Notification, NotificationPreference

logger = logging.getLogger(__name__)


def _send_digests(frequency: str, days: int, label: str):
    """Digest por frecuencia: usuarios con alguna preferencia con
    ``digest_enabled`` a esa frecuencia reciben las no leídas del
    periodo (1 día / 7 días)."""
    if not getattr(settings, "EMAIL_NOTIFICATIONS_ENABLED", False):
        return "Digests deshabilitados (EMAIL_NOTIFICATIONS_ENABLED=false)"
    since = timezone.now() - timedelta(days=days)
    user_ids = (
        NotificationPreference.objects.filter(
            digest_enabled=True, digest_frequency=frequency
        )
        .values_list("user_id", flat=True)
        .distinct()
    )
    frontend_url = getattr(
        settings, "DJANGO_FRONTEND_URL", "http://localhost:5173"
    )
    sent = 0
    for user_id in user_ids.iterator():
        notifications = list(
            Notification.objects.filter(
                recipient_id=user_id,
                read=False,
                created_at__gte=since,
            ).order_by("-created_at")[:50]
        )
        if not notifications:
            continue
        recipient = notifications[0].recipient
        if not recipient.email:
            continue
        lines = "\n".join(f"- {n.title}: {n.body}" for n in notifications)
        html = render_to_string(
            "notifications/email_base.html",
            {
                "title": f"{label}: {len(notifications)} notificaciones",
                "body": lines,
                "action_url": f"{frontend_url}/app/notifications",
                "settings_url": f"{frontend_url}/app/security",
            },
        )
        try:
            msg = EmailMultiAlternatives(
                subject=f"[TODOlist] {label} ({len(notifications)} pendientes)",
                body=lines,
                from_email=getattr(
                    settings, "DEFAULT_FROM_EMAIL", "noreply@todolist.local"
                ),
                to=[recipient.email],
            )
            msg.attach_alternative(html, "text/html")
            msg.send(fail_silently=True)
            sent += 1
        except Exception:
            logger.exception("Error enviando digest a %s", recipient.email)
    return f"Digests enviados: {sent}"


@shared_task
def send_daily_digests():
    """Resumen diario a las 8:00 para usuarios con digest_frequency=daily."""
    return _send_digests("daily", 1, "Resumen diario")


@shared_task
def send_weekly_digests():
    """Resumen semanal (lunes 8:00) para usuarios con digest_frequency=weekly."""
    return _send_digests("weekly", 7, "Resumen semanal")
