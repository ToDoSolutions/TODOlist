"""Servicio para sync offline con conflict resolution (last-write-wins)."""
from django.utils import timezone
from django.db import transaction
import logging

from .models import SyncOperation, SyncDevice

logger = logging.getLogger(__name__)


def register_device(user, device_id, device_name=""):
    """Registra o actualiza un dispositivo."""
    device, created = SyncDevice.objects.update_or_create(
        device_id=device_id,
        defaults={"user": user, "device_name": device_name},
    )
    return device


def apply_sync_operations(user, operations):
    """Aplica operaciones de sync desde un dispositivo offline.

    Cada operación es un dict con:
    - op_type: create/update/delete
    - entity_type: task/project/comment
    - entity_id: UUID del cliente
    - payload: datos
    - client_timestamp: timestamp del cliente

    Retorna lista de resultados con status (applied/conflict/rejected).
    """
    results = []
    for op_data in operations:
        try:
            result = _apply_single_operation(user, op_data)
            results.append(result)
        except Exception as e:
            logger.error(f"Error applying sync op: {e}")
            results.append({
                "entity_id": op_data.get("entity_id"),
                "status": "rejected",
                "error": str(e),
            })
    return results


def _apply_single_operation(user, op_data):
    """Aplica una operación individual con conflict resolution."""
    from apps.tasks.models import Task
    from apps.projects.models import Project
    from django.utils.dateparse import parse_datetime

    op_type = op_data["op_type"]
    entity_type = op_data["entity_type"]
    entity_id = op_data["entity_id"]
    payload = op_data.get("payload", {})
    client_ts = op_data.get("client_timestamp")
    if isinstance(client_ts, str):
        client_ts = parse_datetime(client_ts)

    # Registrar la operación
    sync_op = SyncOperation.objects.create(
        device=SyncDevice.objects.filter(device_id=op_data.get("device_id", "")).first(),
        user=user,
        op_type=op_type,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload,
        client_timestamp=client_ts,
    )

    if entity_type == "task":
        return _apply_task_operation(user, sync_op, op_type, entity_id, payload, client_ts)
    elif entity_type == "project":
        return _apply_project_operation(user, sync_op, op_type, entity_id, payload, client_ts)
    else:
        sync_op.status = SyncOperation.Status.REJECTED
        sync_op.save()
        return {"entity_id": entity_id, "status": "rejected", "error": "Unknown entity type"}


def _apply_task_operation(user, sync_op, op_type, entity_id, payload, client_ts):
    from apps.tasks.models import Task

    if op_type == "create":
        task = Task.objects.create(owner=user, **_filter_task_fields(payload))
        sync_op.server_entity_id = task.id
        sync_op.status = SyncOperation.Status.APPLIED
        sync_op.applied_at = timezone.now()
        sync_op.save()
        return {"entity_id": entity_id, "server_id": task.id, "status": "applied"}

    elif op_type == "update":
        server_id = payload.get("id")
        try:
            task = Task.objects.get(id=server_id, owner=user)
            # Conflict resolution: last-write-wins
            if task.updated_at and client_ts and task.updated_at > client_ts:
                sync_op.status = SyncOperation.Status.CONFLICT
                sync_op.conflict_data = _task_to_dict(task)
                sync_op.save()
                return {"entity_id": entity_id, "status": "conflict", "server_data": _task_to_dict(task)}
            for k, v in _filter_task_fields(payload).items():
                setattr(task, k, v)
            task.save()
            sync_op.server_entity_id = task.id
            sync_op.status = SyncOperation.Status.APPLIED
            sync_op.applied_at = timezone.now()
            sync_op.save()
            return {"entity_id": entity_id, "server_id": task.id, "status": "applied"}
        except Task.DoesNotExist:
            sync_op.status = SyncOperation.Status.REJECTED
            sync_op.save()
            return {"entity_id": entity_id, "status": "rejected", "error": "Task not found"}

    elif op_type == "delete":
        server_id = payload.get("id")
        try:
            task = Task.objects.get(id=server_id, owner=user)
            task.delete()
            sync_op.status = SyncOperation.Status.APPLIED
            sync_op.applied_at = timezone.now()
            sync_op.save()
            return {"entity_id": entity_id, "status": "applied"}
        except Task.DoesNotExist:
            sync_op.status = SyncOperation.Status.REJECTED
            sync_op.save()
            return {"entity_id": entity_id, "status": "rejected", "error": "Task not found"}


def _apply_project_operation(user, sync_op, op_type, entity_id, payload, client_ts):
    from apps.projects.models import Project

    if op_type == "create":
        project = Project.objects.create(owner=user, **_filter_project_fields(payload))
        sync_op.server_entity_id = project.id
        sync_op.status = SyncOperation.Status.APPLIED
        sync_op.applied_at = timezone.now()
        sync_op.save()
        return {"entity_id": entity_id, "server_id": project.id, "status": "applied"}
    elif op_type == "update":
        server_id = payload.get("id")
        try:
            project = Project.objects.get(id=server_id, owner=user)
            for k, v in _filter_project_fields(payload).items():
                setattr(project, k, v)
            project.save()
            sync_op.server_entity_id = project.id
            sync_op.status = SyncOperation.Status.APPLIED
            sync_op.applied_at = timezone.now()
            sync_op.save()
            return {"entity_id": entity_id, "server_id": project.id, "status": "applied"}
        except Project.DoesNotExist:
            sync_op.status = SyncOperation.Status.REJECTED
            sync_op.save()
            return {"entity_id": entity_id, "status": "rejected"}
    elif op_type == "delete":
        server_id = payload.get("id")
        try:
            project = Project.objects.get(id=server_id, owner=user)
            project.delete()
            sync_op.status = SyncOperation.Status.APPLIED
            sync_op.save()
            return {"entity_id": entity_id, "status": "applied"}
        except Project.DoesNotExist:
            sync_op.status = SyncOperation.Status.REJECTED
            sync_op.save()
            return {"entity_id": entity_id, "status": "rejected"}


def _filter_task_fields(payload):
    allowed = {"title", "description", "state", "priority", "due_date", "start_date", "story_points"}
    return {k: v for k, v in payload.items() if k in allowed}


def _filter_project_fields(payload):
    allowed = {"name", "description", "color", "is_archived"}
    return {k: v for k, v in payload.items() if k in allowed}


def _task_to_dict(task):
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "state": task.state,
        "priority": task.priority,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
    }


def get_changes_since(user, last_sync):
    """Retorna cambios en el servidor desde el último sync."""
    from apps.tasks.models import Task
    from apps.projects.models import Project

    tasks = Task.objects.for_user(user).filter(updated_at__gt=last_sync)
    projects = Project.objects.filter(owner=user, updated_at__gt=last_sync)

    return {
        "tasks": [_task_to_dict(t) for t in tasks],
        "projects": [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "color": p.color,
                "is_archived": p.is_archived,
                "updated_at": p.updated_at.isoformat() if p.updated_at else None,
            }
            for p in projects
        ],
    }
