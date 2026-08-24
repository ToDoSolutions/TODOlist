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
    """Envía una notificación por email."""
    try:
        subject = f"[TODOlist] {title}"
        message = body
        if action_url:
            frontend_url = getattr(settings, "DJANGO_FRONTEND_URL", "http://localhost:5173")
            message += f"\n\nVer: {frontend_url}{action_url}"
        send_mail(
            subject=subject,
            message=message,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@todolist.local"),
            recipient_list=[recipient.email],
            fail_silently=True,
        )
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
