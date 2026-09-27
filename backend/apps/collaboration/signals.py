"""Signals para colaboración: menciones en comentarios y auditoría de login."""
from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.projects.models import Project
from apps.tasks.models import Comment, Task

from .audit import log_create, log_delete, log_login, log_login_failed
from .mentions import process_mentions


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


# --- Auditoría de Task y Project (create + delete) ---
#
# Los signals no tienen request context (usuario/IP), así que el actor
# registrado es el owner del recurso (AuditLog.actor admite null). Los
# diffs de update se cubren a nivel de vista (patrón TeamViewSet); aquí
# solo se registran create + delete, que eran el hueco de cobertura.


def _instance_owner(instance):
    """Owner del objeto, tolerando que la fila ya no exista (cascadas)."""
    try:
        return instance.owner
    except Exception:  # noqa: BLE001  # boundary intencional: audit nunca rompe el flujo
        return None


@receiver(post_save, sender=Task)
def audit_task_created(sender, instance, created, **kwargs):
    """Registra la creación de una tarea en el audit log."""
    if not created:
        return
    log_create(
        actor=_instance_owner(instance),
        resource_type="task",
        resource_id=instance.id,
        resource_name=(instance.title or "")[:255],
    )


@receiver(post_delete, sender=Task)
def audit_task_deleted(sender, instance, **kwargs):
    """Registra el borrado de una tarea en el audit log."""
    log_delete(
        actor=_instance_owner(instance),
        resource_type="task",
        resource_id=instance.id,
        resource_name=(instance.title or "")[:255],
        old_values={"title": instance.title},
    )


@receiver(post_save, sender=Project)
def audit_project_created(sender, instance, created, **kwargs):
    """Registra la creación de un proyecto en el audit log."""
    if not created:
        return
    log_create(
        actor=_instance_owner(instance),
        resource_type="project",
        resource_id=instance.id,
        resource_name=(instance.name or "")[:255],
    )


@receiver(post_delete, sender=Project)
def audit_project_deleted(sender, instance, **kwargs):
    """Registra el borrado de un proyecto en el audit log."""
    log_delete(
        actor=_instance_owner(instance),
        resource_type="project",
        resource_id=instance.id,
        resource_name=(instance.name or "")[:255],
        old_values={"name": instance.name},
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
    """Obtiene la IP del cliente desde el request.

    Solo confía en X-Forwarded-For si REMOTE_ADDR es un proxy confiable
    (configurable via DJANGO_TRUSTED_PROXY_IPS).
    """
    import ipaddress

    from django.conf import settings

    remote_addr = request.META.get("REMOTE_ADDR")
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")

    # Lista de proxies confiables (por defecto vacía, configurable)
    trusted_proxies = getattr(settings, "TRUSTED_PROXY_IPS", [])
    is_trusted = False
    if remote_addr and trusted_proxies:
        try:
            remote_ip = ipaddress.ip_address(remote_addr)
            is_trusted = any(
                remote_ip in ipaddress.ip_network(proxy, strict=False)
                for proxy in trusted_proxies
            )
        except ValueError:
            pass

    if x_forwarded_for and is_trusted:
        return x_forwarded_for.split(",")[0].strip()
    return remote_addr
