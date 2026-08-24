"""Servicio para detectar y procesar menciones @user en comentarios."""
import re
from apps.users.models import User
from apps.notifications.services import notify
from .models import Mention


MENTION_PATTERN = re.compile(r"@(\w[\w.]+)")


def extract_mentions(text):
    """Extrae todos los usernames mencionados en un texto."""
    return set(MENTION_PATTERN.findall(text))


def process_mentions(text, comment=None, task=None, mentioned_by=None):
    """Detecta menciones en el texto, crea registros y notifica.

    Retorna la lista de usuarios mencionados.
    """
    if not text:
        return []

    usernames = extract_mentions(text)
    if not usernames:
        return []

    # Buscar usuarios por username o email
    mentioned_users = []
    for username in usernames:
        user = User.objects.filter(username=username).first()
        if not user:
            user = User.objects.filter(email__iexact=username).first()
        if user and user != mentioned_by:
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
            action_url=f"/app/tasks?task={task.id}" if task else "",
        )

    return mentioned_users
