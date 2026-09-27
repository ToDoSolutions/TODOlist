"""Servicio para crear y enviar notificaciones."""
import json
import logging

from django.conf import settings
from django.utils import timezone

from .models import Notification, NotificationPreference, PushSubscription

logger = logging.getLogger(__name__)

# Tipos de notificación que también salen por email cuando el destinatario
# tiene email_enabled en su preferencia para ese tipo. Son los eventos de
# alta señal: asignación, mención y recordatorio puntual de tarea.
EMAIL_NOTIFICATION_TYPES = {
    Notification.Type.TASK_ASSIGNED,
    Notification.Type.MENTION,
    "reminder",
}


def _email_notifications_allowed(notification_type):
    """Gate global + tipo elegible para el canal email.

    Requiere ``settings.EMAIL_NOTIFICATIONS_ENABLED=True`` (opt-in del
    servidor; por defecto desactivado para no enviar ruido con el backend
    console) y que el tipo esté en ``EMAIL_NOTIFICATION_TYPES``.
    """
    return (
        getattr(settings, "EMAIL_NOTIFICATIONS_ENABLED", False)
        and notification_type in EMAIL_NOTIFICATION_TYPES
    )


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

    if (
        pref.email_enabled
        and _email_notifications_allowed(notification_type)
        and _send_email_notification(recipient, title, body, action_url)
        and notification
    ):
        notification.sent_email = True
        notification.save(update_fields=["sent_email"])

    if notification:
        _push_ws_notification(recipient, notification)
        _send_webpush_notifications(recipient, notification)

    return notification


def _send_webpush_notifications(recipient, notification):
    """Envía la notificación por Web Push (VAPID) a las suscripciones del usuario.

    Canal lateral best-effort: nunca rompe ``notify``. Los endpoints
    muertos (HTTP 404/410 del push service) se eliminan para no reintentar
    contra suscripciones obsoletas; el resto de errores solo se loguean.
    """
    private_key = getattr(settings, "VAPID_PRIVATE_KEY", "")
    if not private_key:
        return

    subscriptions = list(recipient.push_subscriptions.all())
    if not subscriptions:
        return

    try:
        from pywebpush import WebPushException, webpush
    except ImportError:  # pragma: no cover - dependencia opcional en runtime
        logger.warning("pywebpush no instalado; Web Push deshabilitado")
        return

    payload = json.dumps({
        "title": notification.title,
        "body": notification.body,
        "url": notification.action_url or "/app",
    })
    claims = {
        "sub": getattr(
            settings, "VAPID_CLAIMS_SUBJECT", "mailto:admin@todolist.local"
        )
    }
    now = timezone.now()

    for sub in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=payload,
                vapid_private_key=private_key,
                vapid_claims=claims,
            )
            PushSubscription.objects.filter(pk=sub.pk).update(last_used_at=now)
        except WebPushException as exc:
            status_code = getattr(
                getattr(exc, "response", None), "status_code", None
            )
            if status_code in (404, 410):
                # Suscripción expirada/dada de baja por el push service
                sub.delete()
                logger.info(
                    "Suscripción Web Push obsoleta eliminada (HTTP %s): %s",
                    status_code,
                    sub.endpoint[:80],
                )
            else:
                logger.warning(
                    "Web Push falló (HTTP %s) para %s: %s",
                    status_code,
                    sub.endpoint[:80],
                    exc,
                )
        except Exception:  # boundary intencional: fallo externo no rompe el flujo
            logger.exception(
                "Error inesperado enviando Web Push a %s", sub.endpoint[:80]
            )


def _push_ws_notification(recipient, notification):
    """Publica la notificación al grupo WebSocket del usuario (tiempo real)."""
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer

        layer = get_channel_layer()
        if not layer:
            return
        async_to_sync(layer.group_send)(
            f"user_{recipient.id}_notifications",
            {
                "type": "notification.new",
                "notification": {
                    "id": notification.id,
                    "type": notification.type,
                    "title": notification.title,
                    "body": notification.body,
                    "action_url": notification.action_url,
                    "created_at": notification.created_at.isoformat(),
                },
            },
        )
        async_to_sync(layer.group_send)(
            f"user_{recipient.id}_notifications",
            {
                "type": "notification.count",
                "count": Notification.objects.filter(
                    recipient=recipient, read=False
                ).count(),
            },
        )
    except Exception:  # noqa: BLE001  # boundary intencional: fallo externo no rompe el flujo
        # Canal no disponible (tests, sin Redis): no romper el notify
        logger.debug("WS push no disponible")


def _send_email_notification(recipient, title, body, action_url):
    """Envía una notificación por email (texto plano + alternativa HTML).

    Devuelve True si el envío se encoló correctamente. Canal best-effort:
    cualquier fallo (template, backend, SMTP) se loguea y devuelve False
    sin propagar — nunca rompe el notify in-app.
    """
    try:
        from django.core.mail import send_mail
        from django.template.loader import render_to_string

        if not recipient.email:
            return False

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

        sent = send_mail(
            subject=subject,
            message=text_message,
            from_email=getattr(
                settings, "DEFAULT_FROM_EMAIL", "noreply@todolist.local"
            ),
            recipient_list=[recipient.email],
            fail_silently=True,
            html_message=html_message,
        )
        return bool(sent)
    except Exception:
        logger.exception(f"Error enviando email a {recipient.email}")
        return False


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
