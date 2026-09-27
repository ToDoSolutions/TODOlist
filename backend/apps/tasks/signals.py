"""Signals del dominio tasks: watchers y multi-asignación.

Complementa a ``apps.notifications.signals`` (que no se toca): aquí se
notifica a los watchers en comentarios y cambios de estado, y a los
nuevos miembros de ``assignees`` la notificación de asignación.
"""
import logging

from django.contrib.auth import get_user_model
from django.db.models.signals import m2m_changed, post_save, pre_save
from django.dispatch import receiver

from .models import Comment, Task

logger = logging.getLogger(__name__)


def _notify(**kwargs):
    """Wrapper perezoso para evitar import circular con notifications."""
    from apps.notifications.services import notify

    return notify(**kwargs)


def _watchers(task, exclude_ids=()):
    """Usuarios watchers de la tarea, excluyendo los ids indicados."""
    return task.watchers.exclude(id__in=set(exclude_ids))


# --- Watchers: comentarios ---


@receiver(post_save, sender=Comment)
def notify_watchers_on_comment(sender, instance, created, **kwargs):
    """Notifica a los watchers cuando hay un comentario nuevo.

    Se salta al autor del comentario y a quienes ya reciben notificación
    por otra vía (owner → task_commented, mencionados → mention).
    """
    if not created:
        return
    task = instance.task
    skip = {instance.author_id, task.owner_id}
    # Los mencionados en el cuerpo ya reciben su notificación "mention"
    body = instance.body or ""
    if "@" in body:
        try:
            from django.db.models import Q

            from apps.collaboration.mentions import extract_mentions

            usernames = extract_mentions(body)
            if usernames:
                skip |= set(
                    get_user_model()
                    .objects.filter(
                        Q(username__in=usernames) | Q(email__in=usernames)
                    )
                    .values_list("id", flat=True)
                )
        except Exception:
            logger.debug("Error calculando mencionados para watchers", exc_info=True)
    for watcher in _watchers(task, exclude_ids=skip):
        _notify(
            recipient=watcher,
            notification_type="task_commented",
            title=f"Nuevo comentario en: {task.title}",
            body=body[:200],
            task=task,
            action_url=f"/app/tasks?task={task.id}",
        )


# --- Watchers: cambios de estado ---


@receiver(pre_save, sender=Task)
def capture_state_for_watchers(sender, instance, raw=False, **kwargs):
    """Captura el estado previo para detectar el cambio en post_save."""
    if raw or not instance.pk:
        instance._old_state_watch = None
        return
    instance._old_state_watch = (
        Task.objects.filter(pk=instance.pk)
        .values_list("state", flat=True)
        .first()
    )


@receiver(post_save, sender=Task)
def notify_watchers_on_state_change(sender, instance, created, **kwargs):
    """Notifica a los watchers cuando la tarea cambia de estado."""
    if created:
        return
    old_state = getattr(instance, "_old_state_watch", None)
    if old_state is None or old_state == instance.state:
        return
    # Actor: el autor del último TaskActivity de cambio de estado (si existe)
    actor_id = (
        instance.activities.filter(action="state_changed")
        .values_list("actor_id", flat=True)
        .first()
    )
    skip = {actor_id} if actor_id else set()
    for watcher in _watchers(instance, exclude_ids=skip):
        _notify(
            recipient=watcher,
            notification_type="task_state_changed",
            title=f"Cambio de estado en: {instance.title}",
            body=f"La tarea '{instance.title}' pasó de {old_state} a {instance.state}",
            task=instance,
            action_url=f"/app/tasks?task={instance.id}",
        )


# --- Multi-assignee: notificación de asignación ---


@receiver(m2m_changed, sender=Task.assignees.through)
def notify_new_assignees(sender, instance, action, pk_set, **kwargs):
    """Notifica la asignación a los NUEVOS miembros de assignees.

    El owner nunca se notifica (misma regla que el assignee FK).
    """
    if action != "post_add" or not pk_set:
        return
    new_ids = set(pk_set) - {instance.owner_id}
    if not new_ids:
        return
    for user in get_user_model().objects.filter(id__in=new_ids):
        _notify(
            recipient=user,
            notification_type="task_assigned",
            title=f"Tarea asignada: {instance.title}",
            body=f"Se te ha asignado la tarea '{instance.title}'",
            task=instance,
            action_url=f"/app/tasks?task={instance.id}",
        )
