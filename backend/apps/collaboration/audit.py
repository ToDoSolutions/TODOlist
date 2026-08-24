"""Servicio de auditoría para registrar cambios sensibles."""
import logging
from .models import AuditLog

logger = logging.getLogger(__name__)


def log_action(
    actor=None,
    action="update",
    resource_type="",
    resource_id=None,
    resource_name="",
    old_values=None,
    new_values=None,
    ip_address=None,
    user_agent="",
):
    """Registra una acción en el log de auditoría."""
    if old_values is None:
        old_values = {}
    if new_values is None:
        new_values = {}

    # Convertir enum a string si es necesario
    if hasattr(action, "value"):
        action = action.value

    try:
        return AuditLog.objects.create(
            actor=actor,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            old_values=old_values,
            new_values=new_values,
            ip_address=ip_address,
            user_agent=user_agent[:500] if user_agent else "",
        )
    except Exception as e:
        logger.error(f"Error creando audit log: {e}", exc_info=True)
        return None


def log_login(user, ip_address=None, user_agent=""):
    log_action(
        actor=user,
        action="login",
        resource_type="user",
        resource_id=user.id if user else None,
        resource_name=user.email if user else "unknown",
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_login_failed(email, ip_address=None, user_agent=""):
    from apps.users.models import User
    user = User.objects.filter(email=email).first()
    log_action(
        actor=user,
        action="login_failed",
        resource_type="user",
        resource_name=email,
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_create(actor, resource_type, resource_id, resource_name, new_values=None):
    return log_action(
        actor=actor,
        action="create",
        resource_type=resource_type,
        resource_id=resource_id,
        resource_name=resource_name,
        new_values=new_values or {},
    )


def log_update(actor, resource_type, resource_id, resource_name, old_values=None, new_values=None):
    return log_action(
        actor=actor,
        action="update",
        resource_type=resource_type,
        resource_id=resource_id,
        resource_name=resource_name,
        old_values=old_values or {},
        new_values=new_values or {},
    )


def log_delete(actor, resource_type, resource_id, resource_name, old_values=None):
    return log_action(
        actor=actor,
        action="delete",
        resource_type=resource_type,
        resource_id=resource_id,
        resource_name=resource_name,
        old_values=old_values or {},
    )


def log_role_change(actor, target_user, old_role, new_role, resource_type="project", resource_id=None):
    return log_action(
        actor=actor,
        action="role_change",
        resource_type=resource_type,
        resource_id=resource_id,
        resource_name=target_user.email,
        old_values={"role": old_role},
        new_values={"role": new_role},
    )
