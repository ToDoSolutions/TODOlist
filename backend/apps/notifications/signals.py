"""Signals que generan notificaciones automáticas."""
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.tasks.models import Comment, Sprint, Task

from .models import Notification
from .services import notify

# La captura pre_save de ``_old_state``/``_old_assignee_id``/
# ``_old_sprint_state`` la hace ``apps.tasks.signals
# .snapshot_task_old_fields``/``snapshot_sprint_old_fields`` — una
# sola consulta compartida por todas las apps.


@receiver(post_save, sender=Comment)
def notify_on_comment(sender, instance, created, **kwargs):
    """Notifica al propietario de la tarea cuando se añade un comentario."""
    if not created:
        return
    task = instance.task
    if task.owner != instance.author:
        notify(
            recipient=task.owner,
            notification_type=Notification.Type.TASK_COMMENTED,
            title=f"Nuevo comentario en: {task.title}",
            body=instance.body[:200],
            task=task,
            action_url=f"/app/tasks/{task.id}",
        )
    # OutgoingWebhook comment_added (del owner de la tarea)
    from apps.events.bus import publish
    publish(
        "comment.created",
        payload={
            "owner_id": task.owner_id,
            "data": {
                "id": instance.id,
                "task_id": task.id,
                "task_title": task.title,
                "author_id": instance.author_id,
                "body": instance.body[:500],
            },
        },
        idempotency_key=f"comment-{instance.id}-created",
    )





@receiver(post_save, sender=Task)
def notify_on_task_assigned(sender, instance, created, **kwargs):
    """Notifica cuando se asigna una tarea (si tiene assignee distinto del owner)."""
    assignee = getattr(instance, "assignee", None)
    if not assignee or assignee == instance.owner:
        return
    if not created and getattr(instance, "_old_assignee_id", None) == instance.assignee_id:
        # Update sin cambio de assignee: no re-notificar
        return
    notify(
        recipient=assignee,
        notification_type=Notification.Type.TASK_ASSIGNED,
        title=f"Tarea asignada: {instance.title}",
        body=f"Se te ha asignado la tarea '{instance.title}'",
        task=instance,
        action_url=f"/app/tasks/{instance.id}",
    )


@receiver(post_save, sender=Sprint)
def notify_on_sprint_state_change(sender, instance, created, **kwargs):
    """Notifica cuando un sprint cambia de estado.

    Solo en la transición real: un save() sobre un sprint ya activo o
    ya cerrado (p.ej. renombrarlo) no debe re-notificar ni re-publicar
    el webhook — antes disparaba en cada save y la idempotency_key con
    timestamp impedía deduplicar en el outbox.
    """
    if created:
        return
    old_state = getattr(instance, "_old_sprint_state", None)
    if (
        instance.state == Sprint.SprintState.ACTIVE
        and old_state != Sprint.SprintState.ACTIVE
    ):
        notify(
            recipient=instance.owner,
            notification_type=Notification.Type.SPRINT_STARTED,
            title=f"Sprint iniciado: {instance.name}",
            body=f"El sprint '{instance.name}' ha comenzado",
            sprint=instance,
            action_url="/app/sprints",
        )
        _publish_sprint_event(instance, "sprint.started")
    elif (
        instance.state == Sprint.SprintState.CLOSED
        and old_state != Sprint.SprintState.CLOSED
    ):
        notify(
            recipient=instance.owner,
            notification_type=Notification.Type.SPRINT_CLOSED,
            title=f"Sprint cerrado: {instance.name}",
            body=f"El sprint '{instance.name}' ha sido cerrado",
            sprint=instance,
            action_url="/app/sprints",
        )
        _publish_sprint_event(instance, "sprint.closed")


def _publish_sprint_event(sprint, event_type):
    """OutgoingWebhook sprint_started/sprint_closed del owner."""
    from apps.events.bus import publish
    publish(
        event_type,
        payload={
            "owner_id": sprint.owner_id,
            "data": {
                "id": sprint.id,
                "name": sprint.name,
                "state": sprint.state,
                "project": sprint.project_id,
            },
        },
        # Key estable (sin timestamp): la transición es única por
        # sprint — el outbox deduplica reintentos/re-saves.
        idempotency_key=f"sprint-{sprint.id}-{event_type}",
    )
