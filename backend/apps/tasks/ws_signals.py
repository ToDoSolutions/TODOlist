"""Signals que emiten eventos WebSocket de tareas a usuarios afectados.

Los efectos externos (push WS, webhooks salientes) se publican en el outbox
transaccional (apps.events) — la fila del evento es atómica con el save() y
los handlers se ejecutan con reintentos si fallan.
"""
import logging

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Task

logger = logging.getLogger(__name__)


def _task_recipients(task):
    """Usuarios a notificar: owner + miembros del proyecto."""
    ids = {task.owner_id}
    if task.project_id:
        # En cascade delete del proyecto, task.project ya no existe en BD:
        # el descriptor haría un query que lanza Project.DoesNotExist.
        from apps.projects.models import Project
        try:
            project = task.project
        except Project.DoesNotExist:
            project = None
        if project is not None:
            ids.update(project.members.values_list("user_id", flat=True))
    return ids


def _task_payload(task):
    return {
        "id": task.id,
        "title": task.title,
        "state": task.state,
        "priority": task.priority,
        "project": task.project_id,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
    }


@receiver(post_save, sender=Task)
def task_saved_ws(sender, instance, created, **kwargs):
    # Métricas de negocio Prometheus
    try:
        from apps.monitoring.metrics import (
            TASK_LEAD_TIME,
            TASKS_COMPLETED,
            TASKS_CREATED,
        )
        if created:
            TASKS_CREATED.inc()
        elif instance.state == "completed" and instance.completed_at:
            TASKS_COMPLETED.inc()
            TASK_LEAD_TIME.observe(
                (instance.completed_at - instance.created_at).total_seconds()
            )
    except Exception:  # las métricas nunca deben romper el flujo
        logger.debug("metrics increment failed", exc_info=True)

    from apps.events.bus import publish
    publish(
        "task.created" if created else "task.updated",
        payload={
            "recipient_ids": list(_task_recipients(instance)),
            "owner_id": instance.owner_id,
            "task": _task_payload(instance),
            "ws_event": {
                "type": "task.created" if created else "task.updated",
                "task": _task_payload(instance),
            },
        },
        idempotency_key=f"task-{instance.id}-{'create' if created else 'upd'}-{instance.updated_at.timestamp() if instance.updated_at else 0}",
    )


@receiver(post_delete, sender=Task)
def task_deleted_ws(sender, instance, **kwargs):
    from apps.events.bus import publish
    publish(
        "task.deleted",
        payload={
            "recipient_ids": list(_task_recipients(instance)),
            "owner_id": instance.owner_id,
            "task": {"id": instance.id},
            "ws_event": {"type": "task.deleted", "task_id": instance.id},
        },
        idempotency_key=f"task-{instance.id}-delete",
    )
