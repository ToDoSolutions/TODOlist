"""Servicio de aplicación para operaciones de Task.

Los canales de entrada (REST, GraphQL, offline sync, GitHub sync) no deben
implementar reglas de negocio por separado: llaman a estas funciones para que
los efectos derivados del estado (completed_at, recurrencia) y las
validaciones de campos se comporten igual en todos los canales.

Las reacciones asíncronas (actividad, notificaciones, WS, automatizaciones)
siguen disparándose por signals sobre el save() resultante.
"""
import logging
from datetime import datetime

from django.utils import timezone

from .models import Task

logger = logging.getLogger(__name__)

UNSET = object()


def normalize_title(title):
    """Título canónico: strip + no vacío + máximo 500 chars."""
    title = (title or "").strip()
    if not title or len(title) > 500:
        raise ValueError("Título inválido")
    return title


def validate_state(state):
    if state not in [c[0] for c in Task.State.choices]:
        raise ValueError(f"Estado inválido: {state}")
    return state


def validate_priority(priority):
    if priority not in [c[0] for c in Task.Priority.choices]:
        raise ValueError(f"Prioridad inválida: {priority}")
    return priority


def parse_due_date(value):
    """ISO 8601 → datetime aware; None/'' → None."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except (ValueError, TypeError):
        raise ValueError("due_date inválida (ISO 8601)")
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed)
    return parsed


def apply_completion_effects(task, save=True):
    """Efectos derivados de task.state tras un cambio.

    - state == completed → completed_at = now + genera la siguiente ocurrencia
      de la recurrencia.
    - state != completed → completed_at = None (reapertura).

    Con save=False solo muta la instancia (el caller decide cuándo guardar,
    p. ej. offline sync dentro de una transacción que ya hace su propio
    save con bump de versión).
    """
    if task.state == Task.State.COMPLETED and not task.completed_at:
        task.completed_at = timezone.now()
        if save:
            task.save(update_fields=["completed_at"])
        if task.recurrence:
            task.generate_next_occurrence()
    elif task.state != Task.State.COMPLETED and task.completed_at:
        task.completed_at = None
        if save:
            task.save(update_fields=["completed_at"])


def assert_state_transition(task, new_state):
    """Si el proyecto tiene workflow definido, exige una transición válida.

    Sin transiciones definidas en el proyecto → comportamiento libre
    (backward compatible). Con workflow → solo aristas permitidas.
    """
    if not task.project_id or task.state == new_state:
        return
    from apps.projects.models import WorkflowTransition
    qs = WorkflowTransition.objects.filter(project_id=task.project_id)
    if not qs.exists():
        return
    if not qs.filter(from_state=task.state, to_state=new_state).exists():
        raise ValueError(
            f"Transición no permitida por el workflow del proyecto: "
            f"{task.state} → {new_state}"
        )


def update_task(task, *, title=UNSET, state=UNSET, priority=UNSET):
    """Aplica cambios básicos validados a una tarea existente.

    Usado por GraphQL y cualquier canal que actualice fuera del serializer
    REST (que tiene su propia validación de invariantes más amplia).
    """
    if title is not UNSET:
        task.title = normalize_title(title)
    if state is not UNSET:
        validate_state(state)
        assert_state_transition(task, state)  # valida contra el estado actual
        task.state = state
    if priority is not UNSET:
        task.priority = validate_priority(priority)
    task.save()
    if state is not UNSET:
        apply_completion_effects(task)
    return task


def get_editable_task(user, task_id):
    """Task editable por el usuario o None (sin distinguir 404/403)."""
    return Task.objects.for_user(user, write=True).filter(id=task_id).first()
