"""Selectors: queries de lectura del dominio tasks.

Primer paso para dar fronteras internas a la god-app: la lógica de
filtrado de listados sale de los ViewSets y se testea de forma aislada.
No mueve modelos ni rompe imports existentes — es una capa fina que los
views delegan.
"""
from django.utils import timezone
from django.utils.dateparse import parse_date

from .models import Sprint, Task


def apply_task_filters(qs, params):
    """Aplica los filtros de querystring del listado de tareas.

    Soporta: due_before, due_after, active_sprint, epic_id, overdue,
    no_due, no_project=true (bandeja de entrada: tareas sin clasificar).
    `project` no puede reutilizarse: es un filterset de django-filter
    y "null" no sería una opción válida.
    """
    if params.get("no_project") == "true":
        # Una tarea homeada en proyectos ya está clasificada
        qs = qs.filter(project__isnull=True).exclude(
            extra_projects__isnull=False
        )

    # Presets estilo Todoist: vencidas (fecha pasada, no terminadas)
    # y sin fecha.
    if params.get("overdue") == "true":
        qs = qs.filter(
            due_date__date__lt=timezone.localdate(),
        ).exclude(
            state__in=(
                Task.State.COMPLETED,
                Task.State.CANCELLED,
                Task.State.ARCHIVED,
            )
        )
    if params.get("no_due") == "true":
        qs = qs.filter(due_date__isnull=True)

    # Tareas marcadas por el escalado SLA (run_daily_checks les pone
    # el tag "sla-breached"). Filterset solo filtra tags por id.
    if params.get("sla_breached") == "true":
        qs = qs.filter(tags__name__iexact="sla-breached").distinct()

    due_before = params.get("due_before")
    due_after = params.get("due_after")
    if due_before:
        d = parse_date(due_before)
        if d:
            qs = qs.filter(due_date__date__lte=d)
    if due_after:
        d = parse_date(due_after)
        if d:
            qs = qs.filter(due_date__date__gte=d)

    if params.get("active_sprint") == "true":
        qs = qs.filter(sprint__state=Sprint.SprintState.ACTIVE)

    epic_id = params.get("epic_id")
    if epic_id and epic_id.isdigit():
        qs = qs.filter(epic_id=int(epic_id))
    return qs
