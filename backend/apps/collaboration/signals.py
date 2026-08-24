"""Signals para colaboración: menciones en comentarios y auditoría de login."""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.utils import timezone

from apps.tasks.models import Comment
from .mentions import process_mentions
from .audit import log_login, log_login_failed


@receiver(post_save, sender=Comment)
def handle_mentions_in_comment(sender, instance, created, **kwargs):
    """Procesa menciones @user cuando se crea o edita un comentario."""
    if not created:
        return
    process_mentions(
        text=instance.body,
        comment=instance,
        task=instance.task,
        mentioned_by=instance.author,
    )


@receiver(user_logged_in)
def audit_login(sender, request, user, **kwargs):
    """Registra el login en el audit log."""
    ip = _get_client_ip(request) if request else None
    ua = request.META.get("HTTP_USER_AGENT", "") if request else ""
    log_login(user, ip_address=ip, user_agent=ua)


@receiver(user_logged_out)
def audit_logout(sender, request, user, **kwargs):
    """Registra el logout en el audit log."""
    from .audit import log_action
    from .models import AuditLog
    ip = _get_client_ip(request) if request else None
    ua = request.META.get("HTTP_USER_AGENT", "") if request else ""
    log_action(
        actor=user,
        action=AuditLog.Action.LOGOUT,
        resource_type="user",
        resource_id=user.id if user else None,
        resource_name=user.email if user else "unknown",
        ip_address=ip,
        user_agent=ua,
    )


@receiver(user_login_failed)
def audit_login_failed(sender, credentials, request, **kwargs):
    """Registra intentos de login fallidos."""
    email = credentials.get("email", credentials.get("username", "unknown"))
    ip = _get_client_ip(request) if request else None
    ua = request.META.get("HTTP_USER_AGENT", "") if request else ""
    log_login_failed(email, ip_address=ip, user_agent=ua)


def _get_client_ip(request):
    """Obtiene la IP del cliente desde el request."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")
