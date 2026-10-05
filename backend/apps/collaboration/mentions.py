"""Servicio para detectar y procesar menciones @user en comentarios."""
import re

from apps.notifications.services import notify
from apps.users.models import User

from .models import Mention

MENTION_PATTERN = re.compile(r"@(\w[\w.]+)")


def extract_mentions(text):
    """Extrae todos los usernames mencionados en un texto."""
    return set(MENTION_PATTERN.findall(text))


MAX_MENTIONS_PER_COMMENT = 20


def _user_can_access_task(user, task):
    """True si el usuario puede ver la tarea (owner o miembro del proyecto)."""
    if not task:
        return True
    if task.owner_id == user.id:
        return True
    if task.project_id:
        if task.project.owner_id == user.id:
            return True
        return task.project.members.filter(user=user).exists()
    return False


def process_mentions(text, comment=None, task=None, mentioned_by=None):
    """Detecta menciones en el texto, crea registros y notifica.

    Solo se notifica a usuarios con acceso a la tarea (evita spam y
    disclosure de existencia de tareas a usuarios sin acceso).
    Limitado a MAX_MENTIONS_PER_COMMENT menciones por comentario.

    Retorna la lista de usuarios mencionados.
    """
    if not text:
        return []

    usernames = list(extract_mentions(text))[:MAX_MENTIONS_PER_COMMENT]
    if not usernames:
        return []

    # Buscar usuarios por username o email
    mentioned_users = []
    for username in usernames:
        user = User.objects.filter(username=username).first()
        if not user:
            user = User.objects.filter(email__iexact=username).first()
        if user and user != mentioned_by and _user_can_access_task(user, task):
            mentioned_users.append(user)

    # Crear registros de mención y notificar
    for user in mentioned_users:
        Mention.objects.create(
            comment=comment,
            task=task,
            mentioned_user=user,
            mentioned_by=mentioned_by,
        )
        notify(
            recipient=user,
            notification_type="mention",
            title=f"Mención de {mentioned_by.email if mentioned_by else 'alguien'}",
            body=f"Te han mencionado en: {task.title if task else 'un comentario'}",
            task=task,
            action_url=f"/app/tasks/{task.id}" if task else "",
        )

    return mentioned_users
