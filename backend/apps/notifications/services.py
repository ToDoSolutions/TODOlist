"""Servicio para crear y enviar notificaciones."""
import logging
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import Notification, NotificationPreference

logger = logging.getLogger(__name__)


def notify(
    recipient,
    notification_type,
    title,
    body="",
    task=None,
    sprint=None,
    action_url="",
    metadata=None,
):
    """Crea una notificación respetando las preferencias del usuario.

    Si el usuario tiene desactivado in_app para ese tipo, no se crea.
    Si tiene email activado, se envía por email también.
    """
    if metadata is None:
        metadata = {}

    # Obtener o crear preferencias por defecto
    pref, _ = NotificationPreference.objects.get_or_create(
        user=recipient,
        notification_type=notification_type,
        defaults={"in_app_enabled": True, "email_enabled": False},
    )

    # Si ambos canales están desactivados, no hacer nada
    if not pref.in_app_enabled and not pref.email_enabled:
        return None

    notification = None
    if pref.in_app_enabled:
        notification = Notification.objects.create(
            recipient=recipient,
            type=notification_type,
            title=title,
            body=body,
            task=task,
            sprint=sprint,
            action_url=action_url,
            metadata=metadata,
            sent_in_app=True,
        )

    if pref.email_enabled:
        _send_email_notification(recipient, title, body, action_url)
        if notification:
            notification.sent_email = True
            notification.save(update_fields=["sent_email"])

    return notification


def _send_email_notification(recipient, title, body, action_url):
    """Envía una notificación por email con template HTML."""
    try:
        from django.template.loader import render_to_string
        from django.core.mail import EmailMultiAlternatives

        subject = f"[TODOlist] {title}"
        frontend_url = getattr(settings, "DJANGO_FRONTEND_URL", "http://localhost:5173")
        full_action_url = f"{frontend_url}{action_url}" if action_url else ""

        # Versión texto plano
        text_message = body
        if full_action_url:
            text_message += f"\n\nVer: {full_action_url}"

        # Versión HTML con template
        html_message = render_to_string("notifications/email_base.html", {
            "title": title,
            "body": body,
            "action_url": full_action_url,
            "settings_url": f"{frontend_url}/app/security",
        })

        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_message,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@todolist.local"),
            to=[recipient.email],
        )
        msg.attach_alternative(html_message, "text/html")
        msg.send(fail_silently=True)
    except Exception as e:
        logger.error(f"Error enviando email a {recipient.email}: {e}")


def mark_as_read(notification_id, user):
    """Marca una notificación como leída."""
    try:
        notif = Notification.objects.get(id=notification_id, recipient=user)
        if not notif.read:
            notif.read = True
            notif.read_at = timezone.now()
            notif.save(update_fields=["read", "read_at"])
        return notif
    except Notification.DoesNotExist:
        return None


def mark_all_as_read(user):
    """Marca todas las notificaciones de un usuario como leídas."""
    now = timezone.now()
    count = Notification.objects.filter(recipient=user, read=False).update(
        read=True, read_at=now
    )
    return count


def get_unread_count(user):
    """Retorna el número de notificaciones no leídas."""
    return Notification.objects.filter(recipient=user, read=False).count()
