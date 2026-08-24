"""Motor de ejecución de reglas de automatización."""
import logging
from datetime import timedelta
from django.utils import timezone

from apps.tasks.models import Task, Sprint
from apps.notifications.services import notify

from .models import AutomationRule, AutomationLog

logger = logging.getLogger(__name__)


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


def execute_action(rule, context):
    """Ejecuta la acción de una regla sobre el contexto dado."""
    action = rule.action
    params = rule.action_params or {}
    result = {}

    task = context.get("task")
    sprint = context.get("sprint")
    user = rule.owner

    if action == AutomationRule.Action.SET_PRIORITY and task:
        priority = int(params.get("priority", 3))
        old_priority = task.priority
        task.priority = priority
        task.save(update_fields=["priority"])
        result = {"old_priority": old_priority, "new_priority": priority}

    elif action == AutomationRule.Action.SET_STATE and task:
        new_state = params.get("state", "pending")
        old_state = task.state
        task.state = new_state
        task.save(update_fields=["state"])
        result = {"old_state": old_state, "new_state": new_state}

    elif action == AutomationRule.Action.SET_DUE_DATE and task:
        days = int(params.get("days_from_now", 7))
        from datetime import date
        task.due_date = date.today() + timedelta(days=days)
        task.save(update_fields=["due_date"])
        result = {"due_date": str(task.due_date)}

    elif action == AutomationRule.Action.MOVE_TO_SPRINT and task:
        sprint_id = params.get("sprint_id")
        if sprint_id:
            try:
                target_sprint = Sprint.objects.get(id=sprint_id, owner=user)
                old_sprint = task.sprint
                task.sprint = target_sprint
                task.save(update_fields=["sprint"])
                result = {"old_sprint": str(old_sprint), "new_sprint": target_sprint.name}
            except Sprint.DoesNotExist:
                result = {"error": f"Sprint {sprint_id} not found"}

    elif action == AutomationRule.Action.SUBTASKS_IN_PROGRESS and task:
        # Mover todas las subtareas pendientes a in_progress
        from apps.tasks.models import Subtask
        subtasks = Subtask.objects.filter(task=task, completed=False)
        count = subtasks.count()
        # Subtask usa completed boolean, no state. Asumimos que "in_progress"
        # se refleja en la tarea padre. Para tareas hijas:
        children = Task.objects.filter(parent=task, state__in=["pending", "backlog"])
        moved = children.update(state="in_progress")
        result = {"moved_subtasks": moved}

    elif action == AutomationRule.Action.CREATE_NOTIFICATION:
        notify(
            recipient=user,
            notification_type="automation_triggered",
            title=params.get("title", f"Automatización: {rule.name}"),
            body=params.get("body", ""),
            task=task,
            sprint=sprint,
            action_url=params.get("action_url", ""),
        )
        result = {"notification_created": True}

    elif action == AutomationRule.Action.CREATE_TASK:
        title = params.get("title", "Tarea creada por automatización")
        new_task = Task.objects.create(
            owner=user,
            title=title,
            description=params.get("description", ""),
            priority=int(params.get("priority", 3)),
            state=params.get("state", "pending"),
        )
        result = {"created_task_id": new_task.id, "created_task_title": new_task.title}

    else:
        result = {"error": f"Action {action} not implemented"}

    return result


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
    """
    if context is None:
        context = {}

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

    results = []
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
            rule.trigger_count += 1
            rule.last_triggered_at = timezone.now()
            rule.save(update_fields=["trigger_count", "last_triggered_at"])

            AutomationLog.objects.create(
                rule=rule,
                status=AutomationLog.Status.SUCCESS,
                trigger_data=_serialize_context(context),
                action_result=action_result,
            )
            results.append({"rule": rule.name, "result": action_result})
        except Exception as e:
            logger.error(f"Error ejecutando regla {rule.name}: {e}")
            AutomationLog.objects.create(
                rule=rule,
                status=AutomationLog.Status.FAILED,
                trigger_data=_serialize_context(context),
                error_message=str(e)[:500],
            )
            results.append({"rule": rule.name, "error": str(e)})

    return results


def run_daily_checks():
    """Chequeo diario: tareas vencidas, sprints por terminar, etc."""
    now = timezone.now()
    results = []

    # Tareas vencidas
    overdue_tasks = Task.objects.filter(
        due_date__lt=now.date(),
        state__in=["pending", "in_progress", "review", "blocked"],
    )
    for task in overdue_tasks:
        r = trigger_automation(
            AutomationRule.Trigger.TASK_OVERDUE,
            {"task": task, "user": task.owner, "due_date": str(task.due_date)},
        )
        if r:
            results.extend(r)

    # Sprints por terminar (end_date en los próximos 2 días)
    soon_sprints = Sprint.objects.filter(
        state=Sprint.SprintState.ACTIVE,
        end_date__lte=now.date() + timedelta(days=2),
    )
    for sprint in soon_sprints:
        r = trigger_automation(
            AutomationRule.Trigger.SPRINT_CLOSED,
            {"sprint": sprint, "user": sprint.owner},
        )
        if r:
            results.extend(r)

    return results
