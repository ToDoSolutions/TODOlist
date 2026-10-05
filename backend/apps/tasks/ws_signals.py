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
    """Usuarios a notificar vía WS: owner + assignee(s) + watchers +
    miembros (y org) de los proyectos donde la tarea vive."""
    ids = {task.owner_id, task.assignee_id}
    try:
        ids.update(task.assignees.values_list("id", flat=True))
        ids.update(task.watchers.values_list("id", flat=True))
    except ValueError:
        pass  # instancia sin pk persistida

    def _members_of(project):
        """Miembros directos + miembros de la organización del proyecto
        (for_user incluye org; sin esto no recibían push)."""
        ids.update(project.members.values_list("user_id", flat=True))
        if project.organization_id:
            ids.update(
                project.organization.memberships.values_list(
                    "user_id", flat=True
                )
            )

    if task.project_id:
        # En cascade delete del proyecto, task.project ya no existe en BD:
        # el descriptor haría un query que lanza Project.DoesNotExist.
        from apps.projects.models import Project
        try:
            project = task.project
        except Project.DoesNotExist:
            project = None
        if project is not None:
            _members_of(project)
    # Multi-homing: miembros (directos y de org) de hogares extra — dos
    # queries sobre la tabla M2M, sin N+1 por proyecto.
    try:
        through = task.extra_projects.through.objects.filter(task=task)
        ids.update(
            through.values_list("project__members__user_id", flat=True)
        )
        ids.update(
            through.values_list(
                "project__organization__memberships__user_id", flat=True
            )
        )
    except Exception:  # post_delete: la M2M puede estar ya purgada
        logger.debug("extra_projects recipients failed", exc_info=True)
    ids.discard(None)
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
