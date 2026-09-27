"""Signals que generan notificaciones automáticas."""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.tasks.models import Comment, Sprint, Task

from .models import Notification
from .services import notify


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
            action_url=f"/app/tasks?task={task.id}",
        )


@receiver(pre_save, sender=Task)
def capture_old_assignee(sender, instance, raw=False, **kwargs):
    """Captura el assignee previo para detectar reasignaciones en post_save."""
    if raw or not instance.pk:
        return
    instance._old_assignee_id = (
        Task.objects.filter(pk=instance.pk)
        .values_list("assignee_id", flat=True)
        .first()
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
        action_url=f"/app/tasks?task={instance.id}",
    )


@receiver(post_save, sender=Sprint)
def notify_on_sprint_state_change(sender, instance, created, **kwargs):
    """Notifica cuando un sprint cambia de estado."""
    if created:
        return
    # Solo notificar si el sprint está activo
    if instance.state == Sprint.SprintState.ACTIVE:
        notify(
            recipient=instance.owner,
            notification_type=Notification.Type.SPRINT_STARTED,
            title=f"Sprint iniciado: {instance.name}",
            body=f"El sprint '{instance.name}' ha comenzado",
            sprint=instance,
            action_url="/app/sprints",
        )
    elif instance.state == Sprint.SprintState.CLOSED:
        notify(
            recipient=instance.owner,
            notification_type=Notification.Type.SPRINT_CLOSED,
            title=f"Sprint cerrado: {instance.name}",
            body=f"El sprint '{instance.name}' ha sido cerrado",
            sprint=instance,
            action_url="/app/sprints",
        )
