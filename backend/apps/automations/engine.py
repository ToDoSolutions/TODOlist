"""Motor de ejecución de reglas de automatización."""
import logging
import threading
from datetime import timedelta

from django.db.models import F
from django.utils import timezone

from apps.notifications.services import notify
from apps.tasks.models import Sprint, Task

from .models import AutomationLog, AutomationRule

logger = logging.getLogger(__name__)

# Profundidad máxima de automatizaciones encadenadas: una acción puede
# disparar signals que vuelven a llamar a trigger_automation (p.ej.
# CREATE_TASK dispara TASK_CREATED). Sin límite, una regla que crea tareas
# en TASK_CREATED se auto-dispara hasta RecursionError.
_MAX_AUTOMATION_DEPTH = 3
_local = threading.local()


def _metric(status):
    try:
        from apps.monitoring.metrics import AUTOMATION_EXECUTIONS
        AUTOMATION_EXECUTIONS.labels(status=status).inc()
    except Exception:  # las métricas nunca deben romper el flujo
        logger.debug("metrics increment failed", exc_info=True)


def evaluate_conditions(conditions, context):
    """Evalúa una lista de condiciones contra un contexto.

    Cada condición: {field, operator, value}
    """
    for cond in conditions:
        field = cond.get("field", "")
        operator = cond.get("operator", "equals")
        expected = cond.get("value", "")
        actual = context.get(field, "")

        if operator == "equals":
            if str(actual) != str(expected):
                return False
        elif operator == "not_equals":
            if str(actual) == str(expected):
                return False
        elif operator == "contains":
            if str(expected) not in str(actual):
                return False
        elif operator == "gt":
            try:
                if not (float(actual) > float(expected)):
                    return False
            except (ValueError, TypeError):
                return False
        elif operator == "lt":
            try:
                if not (float(actual) < float(expected)):
                    return False
            except (ValueError, TypeError):
                return False

    return True


def _valid_priorities():
    return [c[0] for c in Task.Priority.choices] if hasattr(Task, 'Priority') else [1, 2, 3, 4, 5]


def _action_set_priority(rule, params, task, sprint, user):
    try:
        priority = int(params.get("priority", 3))
    except (TypeError, ValueError):
        return {"error": "Invalid priority"}
    if priority not in _valid_priorities():
        return {"error": f"Priority {priority} out of range"}
    old_priority = task.priority
    task.priority = priority
    task.save(update_fields=["priority"])
    return {"old_priority": old_priority, "new_priority": priority}


def _action_set_state(rule, params, task, sprint, user):
    new_state = params.get("state", "pending")
    if new_state not in [c[0] for c in Task.State.choices]:
        return {"error": f"Invalid state '{new_state}'"}
    # Paridad con los otros canales: workflow transitions + efectos de
    # completado (completed_at, siguiente ocurrencia de recurrentes).
    from apps.tasks.services import (
        apply_completion_effects,
        assert_state_transition,
    )
    try:
        assert_state_transition(task, new_state)
    except ValueError as e:
        return {"error": str(e)}
    old_state = task.state
    task.state = new_state
    task.save(update_fields=["state"])
    apply_completion_effects(task)
    return {"old_state": old_state, "new_state": new_state}


def _action_set_due_date(rule, params, task, sprint, user):
    try:
        days = int(params.get("days_from_now", 7))
    except (TypeError, ValueError):
        return {"error": "Invalid days_from_now"}
    if not 0 <= days <= 3650:
        return {"error": "days_from_now out of range (0-3650)"}
    task.due_date = timezone.now() + timedelta(days=days)
    task.save(update_fields=["due_date"])
    return {"due_date": str(task.due_date)}


def _action_move_to_sprint(rule, params, task, sprint, user):
    sprint_id = params.get("sprint_id")
    if not sprint_id:
        return {"skipped": "no sprint_id in action_params"}
    from django.db.models import Q

    from apps.projects.models import accessible_projects

    try:
        # Mismo scope que TaskViewSet.move_to_sprint: sprints propios o
        # de proyectos editables por el owner de la regla.
        target_sprint = Sprint.objects.get(
            Q(owner=user) | Q(project__in=accessible_projects(user, write=True)),
            id=sprint_id,
        )
        # Coherencia: el sprint debe pertenecer al proyecto de la tarea
        if task.project_id and target_sprint.project_id != task.project_id:
            return {"error": "Sprint does not belong to task's project"}
        old_sprint = task.sprint
        task.sprint = target_sprint
        task.save(update_fields=["sprint"])
        return {"old_sprint": str(old_sprint), "new_sprint": target_sprint.name}
    except Sprint.DoesNotExist:
        return {"error": f"Sprint {sprint_id} not found"}


def _action_subtasks_in_progress(rule, params, task, sprint, user):
    # Subtask usa is_done boolean, no state. Mover las tareas hijas
    # pendientes del padre a in_progress — respetando los workflows de
    # su proyecto (una transición prohibida solo salta esa hija).
    from apps.tasks.services import assert_state_transition

    moved = 0
    skipped = 0
    children = Task.objects.filter(
        parent=task, state__in=["pending", "backlog"]
    ).select_related("project")
    for child in children.iterator():
        try:
            assert_state_transition(child, "in_progress")
        except ValueError:
            skipped += 1
            continue
        child.state = "in_progress"
        child.save(update_fields=["state"])
        moved += 1
    return {"moved_subtasks": moved, "skipped_by_workflow": skipped}


def _action_create_notification(rule, params, task, sprint, user):
    notify(
        recipient=user,
        notification_type="automation_triggered",
        title=params.get("title", f"Automatización: {rule.name}"),
        body=params.get("body", ""),
        task=task,
        sprint=sprint,
        action_url=params.get("action_url", ""),
    )
    return {"notification_created": True}


def _action_create_task(rule, params, task, sprint, user):
    title = params.get("title", "Tarea creada por automatización")
    state_param = params.get("state", "pending")
    if state_param not in [c[0] for c in Task.State.choices]:
        state_param = "pending"
    try:
        priority = int(params.get("priority", 3))
    except (TypeError, ValueError):
        priority = 3
    if priority not in _valid_priorities():
        priority = 3
    # Paridad con REST: position al final de la lista del usuario y,
    # si viene project_id (editable por el owner de la regla), seq del
    # proyecto para la ref legible.
    from apps.projects.models import accessible_projects
    from apps.tasks.services import next_position_seq

    project = None
    if params.get("project_id"):
        project = accessible_projects(user, write=True).filter(
            pk=params["project_id"]
        ).first()
        if project is None:
            return {"error": f"Project {params['project_id']} not found or not editable"}
    next_pos, seq = next_position_seq(user, project)
    new_task = Task.objects.create(
        owner=user,
        project=project,
        seq=seq,
        position=next_pos,
        title=str(title)[:500],
        description=str(params.get("description", ""))[:5000],
        priority=priority,
        state=state_param,
    )
    return {"created_task_id": new_task.id, "created_task_title": new_task.title}


def _action_set_assignee(rule, params, task, sprint, user):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    assignee_id = params.get("assignee_id")
    assignee_email = params.get("assignee_email")
    old_assignee = task.assignee
    new_assignee = None
    if assignee_id:
        try:
            new_assignee = User.objects.get(id=assignee_id)
        except User.DoesNotExist:
            return {"error": f"User {assignee_id} not found"}
    elif assignee_email:
        try:
            new_assignee = User.objects.get(email=assignee_email)
        except User.DoesNotExist:
            return {"error": f"User {assignee_email} not found"}
    if not new_assignee:
        return {"skipped": "no assignee_id/assignee_email in action_params"}
    # Verificar que el assignee tiene acceso al proyecto
    if task.project:
        has_access = (
            new_assignee == task.project.owner
            or task.project.members.filter(user=new_assignee).exists()
        )
        if not has_access:
            return {"error": f"User {new_assignee.email} has no access to project"}
    task.assignee = new_assignee
    task.save(update_fields=["assignee"])
    return {
        "old_assignee": str(old_assignee) if old_assignee else None,
        "new_assignee": new_assignee.email,
    }


def _action_add_tag(rule, params, task, sprint, user):
    from apps.tags.models import Tag
    tag_name = params.get("tag_name", "")
    if not tag_name:
        return {"skipped": "no tag_name in action_params"}
    tag, created = Tag.objects.get_or_create(
        name=tag_name,
        owner=user,
        defaults={"color": params.get("tag_color", "#1976d2")},
    )
    task.tags.add(tag)
    return {"tag_added": tag_name, "tag_created": created}


def _action_create_subtask(rule, params, task, sprint, user):
    """Crea un item del checklist (modelo Subtask — el mismo que usa la UI
    de tareas vía POST /tasks/{id}/subtasks/)."""
    from apps.tasks.models import Subtask
    title = str(params.get("title", "")).strip()
    if not title:
        return {"skipped": "no title in action_params"}
    subtask = Subtask.objects.create(task=task, title=title[:255])
    return {"created_subtask_id": subtask.id, "title": subtask.title}


def _action_set_due_offset(rule, params, task, sprint, user):
    """Fija task.due_date = ahora + N días (params: {days})."""
    try:
        days = int(params.get("days"))
    except (TypeError, ValueError):
        return {"error": "Invalid days"}
    if not -3650 <= days <= 3650:
        return {"error": "days out of range (-3650..3650)"}
    task.due_date = timezone.now() + timedelta(days=days)
    task.save(update_fields=["due_date"])
    return {"due_date": str(task.due_date)}


def _action_post_comment(rule, params, task, sprint, user):
    """Publica un comentario en la tarea a nombre del owner de la regla
    (o del owner de la tarea si la regla no tiene owner)."""
    from apps.tasks.models import Comment
    text = str(params.get("text", "")).strip()
    if not text:
        return {"skipped": "no text in action_params"}
    comment = Comment.objects.create(
        task=task, author=user or task.owner, body=text
    )
    return {"comment_id": comment.id}


def _action_call_webhook(rule, params, task, sprint, user):
    """POST a una URL arbitraria: la extensibilidad 'plugin' mínima —
    cualquier automatización puede invocar un endpoint externo (n8n,
    Make, función propia…). action_params: {url, secret?}.

    Mismo endurecimiento que los webhooks salientes: SSRF guard,
    HMAC si hay secret y sin redirects.
    """
    url = str(params.get("url", "")).strip()
    if not url:
        return {"skipped": "no url in action_params"}
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return {"error": "Invalid webhook URL"}
    from apps.integrations_chat.services import _is_safe_url
    if not _is_safe_url(url):
        return {"error": "Webhook URL not allowed (internal destination)"}

    import hashlib
    import hmac
    import json

    import requests
    payload = {
        "event": "automation",
        "rule": rule.name,
        "trigger": rule.trigger,
        "timestamp": timezone.now().isoformat(),
        "task": (
            {
                "id": task.id, "title": task.title, "state": task.state,
                "priority": task.priority, "project_id": task.project_id,
            }
            if task is not None
            else None
        ),
        "sprint": (
            {"id": sprint.id, "name": sprint.name, "state": sprint.state}
            if sprint is not None
            else None
        ),
    }
    body = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    secret = str(params.get("secret", ""))
    if secret:
        headers["X-Hub-Signature-256"] = "sha256=" + hmac.new(
            secret.encode(), body, hashlib.sha256
        ).hexdigest()
    try:
        resp = requests.post(
            url, data=body, headers=headers, timeout=8,
            allow_redirects=False,
        )
    except requests.RequestException as e:
        return {"error": f"webhook request failed: {e.__class__.__name__}"}
    if resp.status_code >= 400:
        return {"error": f"webhook returned HTTP {resp.status_code}"}
    return {"webhook_status": resp.status_code, "url": url}


def _action_move_to_project(rule, params, task, sprint, user):
    """Mueve la tarea a otro proyecto (params: {project_id}).

    El proyecto destino debe ser editable por el owner de la regla
    (misma validación de acceso que usa la API).
    """
    project_id = params.get("project_id")
    if not project_id:
        return {"skipped": "no project_id in action_params"}
    from apps.projects.models import accessible_projects
    target = accessible_projects(user, write=True).filter(
        pk=project_id
    ).first()
    if target is None:
        return {"error": f"Project {project_id} not found or not editable"}
    old_project = task.project
    # Coherencia con el proyecto canónico (misma regla que bulk_update):
    # soltar sprint/epic/section ligados a otro proyecto y quitar el
    # destino de los hogares extra.
    for f in ("sprint", "epic", "section"):
        bound = getattr(task, f"{f}_id", None)
        if bound is not None:
            bound_pid = getattr(getattr(task, f), "project_id", None)
            if bound_pid is not None and bound_pid != target.id:
                setattr(task, f, None)
    task.project = target
    task.save(update_fields=["project", "sprint", "epic", "section"])
    task.extra_projects.remove(target)
    return {
        "old_project": str(old_project) if old_project else None,
        "new_project": target.name,
    }


_ACTION_HANDLERS = {
    AutomationRule.Action.SET_PRIORITY: _action_set_priority,
    AutomationRule.Action.SET_STATE: _action_set_state,
    AutomationRule.Action.SET_DUE_DATE: _action_set_due_date,
    AutomationRule.Action.MOVE_TO_SPRINT: _action_move_to_sprint,
    AutomationRule.Action.SUBTASKS_IN_PROGRESS: _action_subtasks_in_progress,
    AutomationRule.Action.CREATE_NOTIFICATION: _action_create_notification,
    AutomationRule.Action.CREATE_TASK: _action_create_task,
    AutomationRule.Action.SET_ASSIGNEE: _action_set_assignee,
    AutomationRule.Action.ADD_TAG: _action_add_tag,
    AutomationRule.Action.CREATE_SUBTASK: _action_create_subtask,
    AutomationRule.Action.SET_DUE_OFFSET: _action_set_due_offset,
    AutomationRule.Action.POST_COMMENT: _action_post_comment,
    AutomationRule.Action.MOVE_TO_PROJECT: _action_move_to_project,
    AutomationRule.Action.CALL_WEBHOOK: _action_call_webhook,
}


_TASK_ACTIONS = {
    AutomationRule.Action.SET_PRIORITY,
    AutomationRule.Action.SET_STATE,
    AutomationRule.Action.SET_DUE_DATE,
    AutomationRule.Action.MOVE_TO_SPRINT,
    AutomationRule.Action.SUBTASKS_IN_PROGRESS,
    AutomationRule.Action.SET_ASSIGNEE,
    AutomationRule.Action.ADD_TAG,
    AutomationRule.Action.CREATE_SUBTASK,
    AutomationRule.Action.SET_DUE_OFFSET,
    AutomationRule.Action.POST_COMMENT,
    AutomationRule.Action.MOVE_TO_PROJECT,
}


def execute_action(rule, context):
    """Ejecuta la acción de una regla sobre el contexto dado."""
    action = rule.action
    task = context.get("task")
    if action in _TASK_ACTIONS and not task:
        return {"error": f"Action {action} requires a task in context"}
    handler = _ACTION_HANDLERS.get(action)
    if handler is None:
        return {"error": f"Action {action} not implemented"}
    return handler(
        rule,
        rule.action_params or {},
        task,
        context.get("sprint"),
        rule.owner,
    )


def _serialize_context(context):
    """Serializa el contexto para guardarlo en JSONField (sin objetos Django)."""
    serialized = {}
    for key, value in context.items():
        if hasattr(value, "id") and hasattr(value, "__class__"):
            # Es un modelo Django
            serialized[key] = {
                "_type": value.__class__.__name__,
                "id": value.id,
                "str": str(value),
            }
        elif isinstance(value, (str, int, float, bool, list, dict, type(None))):
            serialized[key] = value
        else:
            serialized[key] = str(value)
    return serialized


def trigger_automation(trigger_type, context=None):
    """Ejecuta todas las reglas habilitadas para un trigger dado.

    context debe contener al menos 'user' o 'task' con owner.
    Las acciones pueden disparar nuevas automatizaciones vía signals;
    se limita la profundidad para evitar bucles infinitos.

    Scope deliberado: solo corren las reglas del ``owner`` de la tarea
    (o ``context["user"]``), nunca las del actor que causó el evento —
    las automatizaciones de un miembro no mutan el trabajo de otros en
    proyectos compartidos. Si la semántica deseada fuera "reglas del
    proyecto", habría que añadirlas a nivel proyecto con su modelo
    propio; reutilizar reglas personales sería un bug de aislamiento.
    """
    if context is None:
        context = {}

    depth = getattr(_local, "depth", 0)
    if depth >= _MAX_AUTOMATION_DEPTH:
        logger.warning("Automatización: profundidad máxima alcanzada, posible bucle de reglas")
        return []

    # Determinar el usuario desde el contexto
    user = context.get("user")
    task = context.get("task")
    if not user and task:
        user = task.owner
        context["user"] = user
    if not user:
        return []

    rules = AutomationRule.objects.filter(
        owner=user, trigger=trigger_type, enabled=True
    )

    # Revalidación de permisos: si el usuario perdió acceso al proyecto de la
    # tarea que disparó el trigger, sus reglas no deben actuar sobre ella.
    if task is not None and getattr(task, "project_id", None):
        from apps.projects.models import accessible_projects
        if not accessible_projects(user).filter(pk=task.project_id).exists():
            logger.info(
                "Automatización: usuario %s sin acceso al proyecto %s; reglas omitidas",
                user.pk, task.project_id,
            )
            return []

    results = []
    _local.depth = depth + 1
    try:
        for rule in rules:
            # Evaluar condiciones
            if rule.conditions and not evaluate_conditions(rule.conditions, context):
                AutomationLog.objects.create(
                    rule=rule,
                    status=AutomationLog.Status.SKIPPED,
                    trigger_data=_serialize_context(context),
                )
                continue

            # Ejecutar acción
            try:
                action_result = execute_action(rule, context)
                # Errores semánticos (acción no aplicable al contexto) se
                # registran como FAILED, no como SUCCESS con "error" dentro.
                if isinstance(action_result, dict) and "error" in action_result:
                    AutomationLog.objects.create(
                        rule=rule,
                        status=AutomationLog.Status.FAILED,
                        trigger_data=_serialize_context(context),
                        action_result=action_result,
                        error_message=str(action_result["error"])[:500],
                    )
                    results.append({"rule": rule.name, "result": action_result})
                    _metric("failed")
                    continue
                AutomationRule.objects.filter(pk=rule.pk).update(
                    trigger_count=F("trigger_count") + 1,
                    last_triggered_at=timezone.now(),
                )

                AutomationLog.objects.create(
                    rule=rule,
                    status=AutomationLog.Status.SUCCESS,
                    trigger_data=_serialize_context(context),
                    action_result=action_result,
                )
                results.append({"rule": rule.name, "result": action_result})
                _metric("success")
            except Exception as e:
                logger.exception(f"Error ejecutando regla {rule.name}")
                AutomationLog.objects.create(
                    rule=rule,
                    status=AutomationLog.Status.FAILED,
                    trigger_data=_serialize_context(context),
                    error_message=str(e)[:500],
                )
                _metric("failed")
                results.append({"rule": rule.name, "error": str(e)})
    finally:
        _local.depth = depth

    return results


def _run_sla_escalations(now):
    """Escalado SLA: tareas que superan resolution_hours se escalan.

    - bump_priority: sube un nivel (hasta P0/P1 según la escala)
    - notify: notifica a owner/assignee del incumplimiento
    - Se marca con el tag 'sla-breached' para no re-escalar el mismo
      incumplimiento cada día (la notificación se repite si sigue vencida).
    - response_hours: tareas que siguen en 'pending' pasado el plazo se
      marcan 'sla-no-response' y notifican (una sola vez por tarea).
    """
    from apps.notifications.services import notify
    from apps.tags.models import Tag
    from apps.tasks.models import Task

    from .models import SlaPolicy

    results = []
    policies = SlaPolicy.objects.filter(enabled=True).select_related("owner")
    for policy in policies:
        cutoff = now - timedelta(hours=policy.resolution_hours)
        breached = Task.objects.filter(
            owner=policy.owner,
            priority=policy.priority,
            created_at__lt=cutoff,
        ).exclude(state__in=["completed", "cancelled", "archived"])
        for task in breached.iterator():
            already_marked = task.tags.filter(name="sla-breached").exists()
            escalated = False
            if policy.bump_priority and task.priority > 1 and not already_marked:
                task.priority -= 1
                task.save(update_fields=["priority"])
                escalated = True
            if not already_marked:
                tag, _ = Tag.objects.get_or_create(
                    owner=policy.owner, name="sla-breached"
                )
                task.tags.add(tag)
            if policy.notify_owner:
                notify(
                    task.owner,
                    "sla_breach",
                    f"SLA incumplido: {task.title}",
                    body=f"La tarea supera las {policy.resolution_hours}h de la política '{policy.name}'.",
                    task=task,
                )
            if policy.notify_assignee and task.assignee and task.assignee != task.owner:
                notify(
                    task.assignee,
                    "sla_breach",
                    f"SLA incumplido: {task.title}",
                    body=f"La tarea asignada supera las {policy.resolution_hours}h de la política '{policy.name}'.",
                    task=task,
                )
            results.append({
                "sla_breach": True,
                "task": task.id,
                "policy": policy.id,
                "escalated": escalated,
            })

        # SLA de primera respuesta: tareas que siguen 'pending' pasado
        # response_hours. Una sola notificación por tarea (tag 'sla-no-response').
        response_cutoff = now - timedelta(hours=policy.response_hours)
        unanswered = Task.objects.filter(
            owner=policy.owner,
            priority=policy.priority,
            created_at__lt=response_cutoff,
            state=Task.State.PENDING,
        )
        for task in unanswered.iterator():
            if task.tags.filter(name="sla-no-response").exists():
                continue
            tag, _ = Tag.objects.get_or_create(
                owner=policy.owner, name="sla-no-response"
            )
            task.tags.add(tag)
            if policy.notify_owner:
                notify(
                    task.owner,
                    "sla_breach",
                    f"SLA de respuesta incumplido: {task.title}",
                    body=f"La tarea sigue pendiente tras {policy.response_hours}h de la política '{policy.name}'.",
                    task=task,
                )
            if policy.notify_assignee and task.assignee and task.assignee != task.owner:
                notify(
                    task.assignee,
                    "sla_breach",
                    f"SLA de respuesta incumplido: {task.title}",
                    body=f"La tarea asignada sigue pendiente tras {policy.response_hours}h de la política '{policy.name}'.",
                    task=task,
                )
            results.append({
                "sla_response_breach": True,
                "task": task.id,
                "policy": policy.id,
            })
    return results


def run_daily_checks():
    """Chequeo diario: tareas vencidas, sprints por terminar, etc."""
    now = timezone.now()
    results = []

    # DAILY_CHECK: disparar reglas de chequeo diario genéricas
    # Se ejecuta para cada usuario que tenga reglas DAILY_CHECK habilitadas
    users_with_daily = AutomationRule.objects.filter(
        trigger=AutomationRule.Trigger.DAILY_CHECK,
        enabled=True,
    ).values_list("owner", flat=True).distinct()
    for user_id in users_with_daily:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            continue
        r = trigger_automation(
            AutomationRule.Trigger.DAILY_CHECK,
            {"user": user, "check_time": str(now)},
        )
        if r:
            results.extend(r)

    # Tareas vencidas (iterador: no cargar todas en memoria)
    overdue_tasks = Task.objects.filter(
        due_date__lt=now,
        state__in=["pending", "in_progress", "review", "blocked"],
    ).iterator()
    for task in overdue_tasks:
        r = trigger_automation(
            AutomationRule.Trigger.TASK_OVERDUE,
            {"task": task, "user": task.owner, "due_date": str(task.due_date)},
        )
        if r:
            results.extend(r)

    # SCHEDULED: reglas programadas por intervalo (cada N horas).
    # Se ejecuta la acción directamente por regla (no via trigger_automation,
    # que dispararía TODAS las reglas SCHEDULED del usuario en cada iteración).
    scheduled_rules = AutomationRule.objects.filter(
        trigger=AutomationRule.Trigger.SCHEDULED,
        enabled=True,
    ).select_related("owner")
    for rule in scheduled_rules:
        interval = timedelta(hours=rule.schedule_hours or 24)
        if rule.last_triggered_at and rule.last_triggered_at + interval > now:
            continue  # aún no toca
        context = {"user": rule.owner, "check_time": str(now)}
        try:
            action_result = execute_action(rule, context)
            # Mismo criterio que trigger_automation: un {"error": ...} es
            # FAILED (p.ej. acciones de tarea en reglas SCHEDULED, que no
            # llevan task en contexto).
            failed_result = (
                isinstance(action_result, dict) and "error" in action_result
            )
            if not failed_result:
                AutomationRule.objects.filter(pk=rule.pk).update(
                    trigger_count=F("trigger_count") + 1,
                    last_triggered_at=now,
                )
            AutomationLog.objects.create(
                rule=rule,
                status=(
                    AutomationLog.Status.FAILED
                    if failed_result
                    else AutomationLog.Status.SUCCESS
                ),
                trigger_data=_serialize_context(context),
                action_result=action_result,
                error_message=str(action_result.get("error", ""))[:500]
                if failed_result
                else "",
            )
            results.append({"rule": rule.name, "result": action_result})
            _metric("failed" if failed_result else "success")
        except Exception as e:
            logger.exception(f"Error ejecutando regla programada {rule.name}")
            AutomationLog.objects.create(
                rule=rule,
                status=AutomationLog.Status.FAILED,
                trigger_data=_serialize_context(context),
                error_message=str(e)[:500],
            )
            _metric("failed")

    # SLA: escalado de tareas que superan el resolution_hours de su política
    sla_results = _run_sla_escalations(now)
    results.extend(sla_results)

    # Sprints por terminar (end_date en los próximos 2 días)
    soon_sprints = Sprint.objects.filter(
        state=Sprint.SprintState.ACTIVE,
        end_date__lte=now.date() + timedelta(days=2),
    )
    for sprint in soon_sprints:
        # Dedup por sprint: esta tarea corre cada hora y el sprint sigue
        # activo hasta 2 días — sin esto las reglas se re-disparan 24×.
        already_fired = AutomationLog.objects.filter(
            rule__owner=sprint.owner,
            rule__trigger=AutomationRule.Trigger.SPRINT_CLOSED,
            trigger_data__sprint_id=sprint.id,
        ).exists()
        if already_fired:
            continue
        r = trigger_automation(
            AutomationRule.Trigger.SPRINT_CLOSED,
            {
                "sprint": sprint,
                "sprint_id": sprint.id,
                "user": sprint.owner,
            },
        )
        if r:
            results.extend(r)

    return results
