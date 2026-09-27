"""Servicio para sync offline con conflict resolution (last-write-wins)."""
import logging

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from .models import SyncDevice, SyncOperation

logger = logging.getLogger(__name__)


def register_device(user, device_id, device_name=""):
    """Registra o actualiza un dispositivo.

    Un device_id ya registrado por OTRO usuario no puede reasignarse
    (evita hijacking de dispositivos ajenos).
    """
    existing = SyncDevice.objects.filter(device_id=device_id).first()
    if existing and existing.user_id != user.id:
        raise PermissionDenied("device_id ya registrado por otro usuario")
    if existing:
        existing.device_name = device_name or existing.device_name
        existing.is_active = True
        existing.save(update_fields=["device_name", "is_active"])
        return existing
    return SyncDevice.objects.create(
        user=user, device_id=device_id, device_name=device_name
    )


MAX_SYNC_OPERATIONS = 500


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
    if not isinstance(operations, list) or len(operations) > MAX_SYNC_OPERATIONS:
        raise ValueError(f"Máximo {MAX_SYNC_OPERATIONS} operaciones por push")

    # Validar dispositivos: solo dispositivos activos del propio usuario
    device_ids = {op.get("device_id") for op in operations if op.get("device_id")}
    if device_ids:
        valid_ids = set(
            SyncDevice.objects.filter(
                device_id__in=device_ids, user=user, is_active=True
            ).values_list("device_id", flat=True)
        )
        invalid = device_ids - valid_ids
        if invalid:
            raise PermissionDenied(
                f"Dispositivos no válidos o revocados: {sorted(invalid)}"
            )

    results = []
    for op_data in operations:
        try:
            result = _apply_single_operation(user, op_data)
            results.append(result)
        except Exception as e:
            logger.exception("Error applying sync op")
            results.append({
                "entity_id": op_data.get("entity_id"),
                "status": "rejected",
                "error": str(e)[:300],
            })
    return results


def _apply_single_operation(user, op_data):
    """Aplica una operación individual con conflict resolution."""
    from django.utils.dateparse import parse_datetime

    op_type = op_data["op_type"]
    entity_type = op_data["entity_type"]
    entity_id = op_data["entity_id"]
    payload = op_data.get("payload", {})
    client_ts = op_data.get("client_timestamp")
    if isinstance(client_ts, str):
        client_ts = parse_datetime(client_ts)
    base_version = op_data.get("base_version")

    # Registrar la operación
    sync_op = SyncOperation.objects.create(
        device=SyncDevice.objects.filter(
            device_id=op_data.get("device_id", ""), user=user
        ).first(),
        user=user,
        op_type=op_type,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload,
        client_timestamp=client_ts,
        base_version=base_version,
    )

    if entity_type == "task":
        return _apply_task_operation(
            user, sync_op, op_type, entity_id, payload, client_ts,
            base_version, base_fields=op_data.get("base_fields") or {},
        )
    elif entity_type == "project":
        return _apply_project_operation(user, sync_op, op_type, entity_id, payload, client_ts)
    else:
        sync_op.status = SyncOperation.Status.REJECTED
        sync_op.save()
        return {"entity_id": entity_id, "status": "rejected", "error": "Unknown entity type"}


def _apply_task_operation(user, sync_op, op_type, entity_id, payload, client_ts, base_version=None, base_fields=None):
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
        # Sin base_version no hay detección de conflictos: rechazar
        if base_version is None:
            sync_op.status = SyncOperation.Status.REJECTED
            sync_op.save()
            return {"entity_id": entity_id, "status": "rejected", "error": "base_version required"}
        try:
            with transaction.atomic():
                task = Task.objects.select_for_update().get(id=server_id, owner=user)

                # Conflict detection by version: si base_version < current_version
                # hay conflicto (el recurso fue modificado en el servidor después
                # de que el cliente obtuvo su copia)
                if task.version is not None and base_version < task.version:
                    # Merge por campo: con `base_fields` (snapshot del cliente
                    # de los campos que toca) solo hay conflicto en campos que
                    # el servidor cambió Y el cliente también modifica.
                    if base_fields:
                        changes = _filter_task_fields(payload)
                        conflicts = _field_conflicts(task, base_fields, changes)
                        if not conflicts:
                            # El servidor tocó otros campos: merge seguro
                            from apps.tasks.services import apply_completion_effects
                            for k, v in changes.items():
                                setattr(task, k, v)
                            apply_completion_effects(task, save=False)
                            task.save()
                            sync_op.server_entity_id = task.id
                            sync_op.status = SyncOperation.Status.APPLIED
                            sync_op.applied_at = timezone.now()
                            sync_op.save()
                            try:
                                from apps.monitoring.metrics import SYNC_CONFLICTS
                                SYNC_CONFLICTS.labels(resolution="field_merge").inc()
                            except Exception:
                                logger.debug("metrics increment failed", exc_info=True)
                            return {
                                "entity_id": entity_id,
                                "server_id": task.id,
                                "status": "applied",
                                "merged": True,
                                "current_version": task.version,
                            }
                        sync_op.conflict_data = {
                            "server": _task_to_dict(task),
                            "conflicting_fields": conflicts,
                        }
                    else:
                        sync_op.conflict_data = _task_to_dict(task)
                    sync_op.status = SyncOperation.Status.CONFLICT
                    sync_op.conflict_status = SyncOperation.ConflictStatus.CONFLICT
                    sync_op.save()
                    try:
                        from apps.monitoring.metrics import SYNC_CONFLICTS
                        SYNC_CONFLICTS.labels(resolution="server_wins").inc()
                    except Exception:  # las métricas nunca deben romper el flujo
                        logger.debug("metrics increment failed", exc_info=True)
                    return {
                        "entity_id": entity_id,
                        "conflict": True,
                        "current_version": task.version,
                        "client_version": base_version,
                        "server_data": _task_to_dict(task),
                        "status": "conflict",
                    }

                # Sin conflicto por versión: aplicar el cambio e incrementar versión
                from apps.tasks.services import apply_completion_effects
                for k, v in _filter_task_fields(payload).items():
                    setattr(task, k, v)
                # Efectos de completado (completed_at/recurrencia) antes del
                # save para no hacer un segundo bump de versión.
                apply_completion_effects(task, save=False)
                task.save()  # save() incrementa version automáticamente
            sync_op.server_entity_id = task.id
            sync_op.status = SyncOperation.Status.APPLIED
            sync_op.applied_at = timezone.now()
            sync_op.save()
            return {"entity_id": entity_id, "server_id": task.id, "status": "applied", "current_version": task.version}
        except Task.DoesNotExist:
            sync_op.status = SyncOperation.Status.REJECTED
            sync_op.save()
            return {"entity_id": entity_id, "status": "rejected", "error": "Task not found"}

    elif op_type == "delete":
        server_id = payload.get("id")
        if base_version is None:
            sync_op.status = SyncOperation.Status.REJECTED
            sync_op.save()
            return {"entity_id": entity_id, "status": "rejected", "error": "base_version required"}
        try:
            with transaction.atomic():
                task = Task.objects.select_for_update().get(id=server_id, owner=user)

                # Conflict detection by version para delete
                if task.version is not None and base_version < task.version:
                    sync_op.status = SyncOperation.Status.CONFLICT
                    sync_op.conflict_status = SyncOperation.ConflictStatus.CONFLICT
                    sync_op.conflict_data = _task_to_dict(task)
                    sync_op.save()
                    try:
                        from apps.monitoring.metrics import SYNC_CONFLICTS
                        SYNC_CONFLICTS.labels(resolution="server_wins").inc()
                    except Exception:  # las métricas nunca deben romper el flujo
                        logger.debug("metrics increment failed", exc_info=True)
                    return {
                        "entity_id": entity_id,
                        "conflict": True,
                        "current_version": task.version,
                        "client_version": base_version,
                        "server_data": _task_to_dict(task),
                        "status": "conflict",
                    }

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


def _field_conflicts(task, base_fields, changes):
    """Campos donde servidor y cliente divergen.

    Para cada campo que el cliente modifica (changes), compara el valor base
    que vio el cliente (base_fields) con el valor actual del servidor:
    distinto → el servidor tocó ese campo → conflicto real.
    """
    current = _task_to_dict(task)
    conflicts = []
    for field, client_val in changes.items():
        base_val = base_fields.get(field)
        server_val = current.get(field)
        # Comparación laxa (serializado) — ISO datetimes y tipos primitivos
        if str(server_val) != str(base_val):
            conflicts.append({
                "field": field,
                "base": base_val,
                "server": server_val,
                "client": client_val,
            })
    return conflicts


def _task_to_dict(task):
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "state": task.state,
        "priority": task.priority,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        "version": task.version,
    }


def get_changes_since(user, last_sync):
    """Retorna cambios en el servidor desde el último sync."""
    from apps.projects.models import Project
    from apps.tasks.models import Task

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
