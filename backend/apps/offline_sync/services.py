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
    (evita hijacking de dispositivos ajenos). get_or_create + retry en
    IntegrityError cubre la carrera entre el check y el create
    (device_id es unique).
    """
    from django.db import IntegrityError

    try:
        existing, created = SyncDevice.objects.get_or_create(
            device_id=device_id,
            defaults={"user": user, "device_name": device_name},
        )
    except IntegrityError:
        # Perdedor de la carrera: la fila ya existe, releerla.
        existing = SyncDevice.objects.get(device_id=device_id)
        created = False
    if existing.user_id != user.id:
        raise PermissionDenied("device_id ya registrado por otro usuario")
    if not created:
        existing.device_name = device_name or existing.device_name
        existing.is_active = True
        existing.save(update_fields=["device_name", "is_active"])
    return existing


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


def _validate_task_changes(task, changes):
    """Paridad con REST/GraphQL sobre el campo ``state``.

    - ``validate_state``: el valor debe ser un Task.State conocido (el
      whitelist de campos acepta cualquier string sin ella).
    - ``assert_state_transition``: si el proyecto define workflow, la
      arista origen→destino debe existir (antes un cliente offline
      podía saltarse el workflow entero).

    Devuelve mensaje de error para rechazar la op, o None.
    """
    if "state" not in changes:
        return None
    from apps.tasks.services import assert_state_transition, validate_state
    try:
        validate_state(changes["state"])
        if task is not None:  # create: no hay estado origen que validar
            assert_state_transition(task, changes["state"])
    except ValueError as e:
        return str(e)
    return None


def _apply_task_operation(user, sync_op, op_type, entity_id, payload, client_ts, base_version=None, base_fields=None):
    from apps.tasks.models import Task

    if op_type == "create":
        # El proyecto y los hogares extra exigen write-access validado
        extra_ids = _validated_extra_projects(user, payload)
        if extra_ids is None:
            sync_op.status = SyncOperation.Status.REJECTED
            sync_op.save()
            return {"entity_id": entity_id, "status": "rejected",
                    "error": "extra_projects not editable"}
        fields = _filter_task_fields(payload)
        error = _validate_task_changes(None, fields)
        if error:
            sync_op.status = SyncOperation.Status.REJECTED
            sync_op.save()
            return {"entity_id": entity_id, "status": "rejected",
                    "error": error}
        project_id = payload.get("project") or payload.get("project_id")
        if project_id is not None:
            from apps.projects.models import accessible_projects
            if not accessible_projects(user, write=True).filter(
                pk=project_id
            ).exists():
                return {"entity_id": entity_id, "status": "rejected",
                        "error": "project not editable"}
            fields["project_id"] = project_id
        # Paridad de canales: position/seq asignados en servidor (el
        # whitelist de campos no los admite desde el cliente).
        from apps.tasks.services import next_position_seq
        project = None
        if fields.get("project_id"):
            from apps.projects.models import Project
            project = Project.objects.filter(pk=fields["project_id"]).first()
        pos, seq = next_position_seq(user, project)
        fields.setdefault("position", pos)
        fields.setdefault("seq", seq)
        task = Task.objects.create(owner=user, **fields)
        if extra_ids:
            task.extra_projects.set(extra_ids)
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
                # Paridad con REST/GraphQL: basta write-access, no
                # ownership (proyectos compartidos, multi-homing)
                task = Task.objects.for_user(user, write=True).filter(
                    pk=server_id
                ).select_for_update().first()
                if task is None:
                    raise Task.DoesNotExist

                # Conflict detection by version: si base_version < current_version
                # hay conflicto (el recurso fue modificado en el servidor después
                # de que el cliente obtuvo su copia)
                if task.version is not None and base_version < task.version:
                    # Merge por campo: con `base_fields` (snapshot del cliente
                    # de los campos que toca) solo hay conflicto en campos que
                    # el servidor cambió Y el cliente también modifica.
                    if base_fields:
                        changes = _filter_task_fields(payload)
                        error = _validate_task_changes(task, changes)
                        if error:
                            sync_op.status = SyncOperation.Status.REJECTED
                            sync_op.save()
                            return {"entity_id": entity_id,
                                    "status": "rejected", "error": error}
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
                changes = _filter_task_fields(payload)
                error = _validate_task_changes(task, changes)
                if error:
                    sync_op.status = SyncOperation.Status.REJECTED
                    sync_op.save()
                    return {"entity_id": entity_id, "status": "rejected",
                            "error": error}
                for k, v in changes.items():
                    setattr(task, k, v)
                # Hogares extra y proyecto canónico (M2M/FK no cubiertos
                # por el merge por campo)
                if "extra_projects" in payload:
                    extra = _validated_extra_projects(
                        user, payload,
                        canonical=payload.get("project")
                        or payload.get("project_id")
                        or task.project_id,
                    )
                    if extra is None:
                        sync_op.status = SyncOperation.Status.REJECTED
                        sync_op.save()
                        return {"entity_id": entity_id, "status": "rejected",
                                "error": "extra_projects not editable"}
                    task.extra_projects.set(extra)
                if "project" in payload or "project_id" in payload:
                    from apps.projects.models import accessible_projects
                    new_pid = payload.get("project") or payload.get("project_id")
                    if new_pid is not None and not accessible_projects(
                        user, write=True
                    ).filter(pk=new_pid).exists():
                        sync_op.status = SyncOperation.Status.REJECTED
                        sync_op.save()
                        return {"entity_id": entity_id, "status": "rejected",
                                "error": "project not editable"}
                    task.project_id = new_pid
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
                task = Task.objects.for_user(user, write=True).filter(
                    pk=server_id
                ).select_for_update().first()
                if task is None:
                    raise Task.DoesNotExist

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


def _validated_extra_projects(user, payload, canonical=None):
    """IDs válidos para `extra_projects`: write-access sobre cada uno y
    distintos del proyecto canónico (del payload o el ya persistido).

    None si `extra_projects` está presente pero algún id no es editable
    ni válido — el caller rechaza la operación. [] si la clave no viene.
    """
    ids = payload.get("extra_projects")
    if ids is None:
        return []
    if not isinstance(ids, list):
        return None
    canonical = (
        canonical
        if canonical is not None
        else (payload.get("project") or payload.get("project_id"))
    )
    from apps.projects.models import accessible_projects
    allowed = set(
        accessible_projects(user, write=True).values_list("pk", flat=True)
    )
    if any(i not in allowed or i == canonical for i in ids):
        return None
    return ids


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
        "project": task.project_id,
        "extra_projects": [
            ep.pk if hasattr(ep, "pk") else ep
            for ep in task.extra_projects.all()
        ],
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        "version": task.version,
    }


MAX_PULL_TASKS = 2000
MAX_PULL_PROJECTS = 500
MAX_PULL_TOMBSTONES = 2000


def get_changes_since(user, last_sync):
    """Retorna cambios en el servidor desde el último sync.

    Incluye ``deleted_task_ids`` (tombstones a partir de los eventos
    ``task.deleted`` del outbox — sin ellos las tareas borradas
    desaparecían del pull y el cliente conservaba copias zombies) y
    ``truncated`` cuando el pull llega al cap de tareas (el cliente
    debe pedir una ventana más estrecha o rehidratarse).
    """
    from apps.events.models import OutboxEvent
    from apps.projects.models import accessible_projects
    from apps.tasks.models import Task

    # Un "since" ISO sin offset llega naive — compararlo con campos
    # aware lanzaba error o silencio según el backend de BD.
    if timezone.is_naive(last_sync):
        last_sync = timezone.make_aware(last_sync)

    tasks = list(
        Task.objects.for_user(user)
        .filter(updated_at__gt=last_sync)
        .prefetch_related("extra_projects")
        .order_by("updated_at", "id")[:MAX_PULL_TASKS]
    )
    # Proyectos accesibles (miembros incluidos), no solo propios — un
    # proyecto compartido editado por otro miembro nunca llegaba al pull.
    projects = accessible_projects(user).filter(
        updated_at__gt=last_sync
    ).order_by("updated_at", "id")[:MAX_PULL_PROJECTS]
    tombstones = list(
        OutboxEvent.objects.filter(
            event_type="task.deleted",
            created_at__gt=last_sync,
            payload__owner_id=user.id,
        ).values_list("payload__task__id", flat=True)[:MAX_PULL_TOMBSTONES]
    )

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
        "deleted_task_ids": [tid for tid in tombstones if tid is not None],
        "truncated": len(tasks) == MAX_PULL_TASKS,
    }
