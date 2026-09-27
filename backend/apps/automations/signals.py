"""Signals que disparan automatizaciones según eventos del dominio.

Cablea los triggers de AutomationRule a los eventos reales del modelo:
- TASK_CREATED: al crear una tarea
- TASK_STATE_CHANGED: al cambiar el estado de una tarea
- TASK_COMPLETED: al pasar a estado completed
- TASK_BLOCKED: al pasar a estado blocked
- COMMENT_ADDED: al crear un comentario
- SPRINT_STARTED: al iniciar un sprint (cambio a active)
- SPRINT_CLOSED: al cerrar un sprint (cambio a closed)
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.tasks.models import Comment, Sprint, Task

from .engine import trigger_automation
from .models import AutomationRule

# --- Tarea ---

@receiver(pre_save, sender=Task)
def _capture_task_state(sender, instance, **kwargs):
    """Guarda el estado previo de la tarea para comparar en post_save."""
    if instance.pk:
        instance._old_state = (
            Task.objects.filter(pk=instance.pk)
            .values_list("state", flat=True)
            .first()
        )
    else:
        instance._old_state = None


@receiver(post_save, sender=Task)
def task_automation_signals(sender, instance, created, **kwargs):
    """Dispara TASK_CREATED al crear y TASK_STATE_CHANGED al cambiar de estado."""
    if created:
        trigger_automation(
            AutomationRule.Trigger.TASK_CREATED,
            {"task": instance, "user": instance.owner},
        )
        return

    old_state = getattr(instance, "_old_state", None)
    if old_state is not None and old_state != instance.state:
        trigger_automation(
            AutomationRule.Trigger.TASK_STATE_CHANGED,
            {
                "task": instance,
                "user": instance.owner,
                "old_state": old_state,
                "new_state": instance.state,
            },
        )
        # Triggers específicos por estado destino
        if instance.state == Task.State.COMPLETED:
            trigger_automation(
                AutomationRule.Trigger.TASK_COMPLETED,
                {
                    "task": instance,
                    "user": instance.owner,
                    "old_state": old_state,
                },
            )
        elif instance.state == Task.State.BLOCKED:
            trigger_automation(
                AutomationRule.Trigger.TASK_BLOCKED,
                {
                    "task": instance,
                    "user": instance.owner,
                    "old_state": old_state,
                },
            )


# --- Comentario ---

@receiver(post_save, sender=Comment)
def comment_automation_signal(sender, instance, created, **kwargs):
    """Dispara COMMENT_ADDED cuando se crea un comentario."""
    if not created:
        return
    task = instance.task
    trigger_automation(
        AutomationRule.Trigger.COMMENT_ADDED,
        {
            "task": task,
            "user": task.owner,
            "comment": instance,
            "author": instance.author,
        },
    )


# --- Sprint ---

@receiver(pre_save, sender=Sprint)
def _capture_sprint_state(sender, instance, **kwargs):
    """Guarda el estado previo del sprint para comparar en post_save."""
    if instance.pk:
        instance._old_sprint_state = (
            Sprint.objects.filter(pk=instance.pk)
            .values_list("state", flat=True)
            .first()
        )
    else:
        instance._old_sprint_state = None


@receiver(post_save, sender=Sprint)
def sprint_automation_signal(sender, instance, created, **kwargs):
    """Dispara SPRINT_STARTED al activar y SPRINT_CLOSED al cerrar un sprint."""
    if created:
        return
    old_state = getattr(instance, "_old_sprint_state", None)
    # SPRINT_STARTED: sprint pasa a estado active
    if (
        old_state != Sprint.SprintState.ACTIVE
        and instance.state == Sprint.SprintState.ACTIVE
    ):
        trigger_automation(
            AutomationRule.Trigger.SPRINT_STARTED,
            {"sprint": instance, "user": instance.owner},
        )
    # SPRINT_CLOSED: sprint pasa a estado closed
    if (
        old_state != Sprint.SprintState.CLOSED
        and instance.state == Sprint.SprintState.CLOSED
    ):
        trigger_automation(
            AutomationRule.Trigger.SPRINT_CLOSED,
            {"sprint": instance, "user": instance.owner},
        )
