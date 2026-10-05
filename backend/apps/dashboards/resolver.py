"""Resolver de widgets: produce los datos de cada tipo de widget."""
from datetime import timedelta

from django.utils import timezone

from apps.tasks.models import Task

OPEN = ["backlog", "pending", "in_progress", "review", "blocked"]


def _task_brief(t):
    return {
        "id": t.id, "title": t.title, "state": t.state,
        "priority": t.priority,
        "due_date": t.due_date.isoformat() if t.due_date else None,
    }


def w_my_tasks(user, config):
    """Mis tareas abiertas asignadas a mí."""
    qs = Task.objects.for_user(user).filter(
        assignee=user, state__in=OPEN
    ).order_by("due_date")[:int(config.get("limit", 10))]
    return {"tasks": [_task_brief(t) for t in qs]}


def w_overdue(user, config):
    """Tareas vencidas (mías o que poseo)."""
    qs = Task.objects.for_user(user).filter(
        due_date__lt=timezone.now(), state__in=OPEN
    ).order_by("due_date")[:int(config.get("limit", 10))]
    return {"tasks": [_task_brief(t) for t in qs], "count": qs.count()}


def w_kpis(user, config):
    """KPIs rápidos: abiertas, vencidas, en progreso, completadas (30d)."""
    base = Task.objects.for_user(user)
    thirty = timezone.now() - timedelta(days=30)
    return {
        "open": base.filter(state__in=OPEN).count(),
        "overdue": base.filter(
            due_date__lt=timezone.now(), state__in=OPEN).count(),
        "in_progress": base.filter(state="in_progress").count(),
        "completed_30d": base.filter(
            state="completed", completed_at__gte=thirty).count(),
    }


def w_blocked(user, config):
    """Tareas bloqueadas por dependencias."""
    from apps.tasks.models import TaskRelation
    base = Task.objects.for_user(user).filter(state__in=OPEN)
    rels = TaskRelation.objects.filter(
        target__in=base,
        relation_type=TaskRelation.RelationType.BLOCKS,
        source__state__in=OPEN,
    ).select_related("source", "target")[:int(config.get("limit", 10))]
    return {
        "blocked": [{
            "task": _task_brief(r.target),
            "blocked_by": _task_brief(r.source),
        } for r in rels],
    }


def w_workload(user, config):
    """Carga por miembro (reusa advanced_metrics)."""
    from apps.tasks.advanced_metrics import get_workload_data
    return {"members": get_workload_data(user)[:int(config.get("limit", 10))]}


def w_velocity(user, config):
    """Velocity de los últimos sprints (+ estimado vs real por sprint)."""
    from apps.tasks.advanced_metrics import get_velocity_data
    data = get_velocity_data(user)
    limit = int(config.get("limit", 6))
    return {
        "sprints": data.get("velocity", [])[:limit],
        "estimated_vs_actual": data.get("estimated_vs_actual", [])[:limit],
    }


def w_prs_open(user, config):
    """PRs abiertas de los repos del usuario."""
    from apps.integrations.models import GitHubPullRequest
    prs = GitHubPullRequest.objects.filter(
        repo__installation__user=user, state="open",
    )[:int(config.get("limit", 10))]
    return {
        "prs": [{
            "repo": p.repo.full_name, "number": p.pr_number,
            "title": p.title, "url": p.html_url,
            "ci_status": p.ci_status,
        } for p in prs],
    }


def w_upcoming_deadlines(user, config):
    """Próximas entregas (7 días)."""
    now = timezone.now()
    qs = Task.objects.for_user(user).filter(
        due_date__gte=now, due_date__lte=now + timedelta(days=7),
        state__in=OPEN,
    ).order_by("due_date")[:int(config.get("limit", 10))]
    return {"tasks": [_task_brief(t) for t in qs]}


def w_recent_activity(user, config):
    """Actividad reciente del usuario (últimas acciones)."""
    from apps.collaboration.models import AuditLog
    logs = AuditLog.objects.filter(
        actor=user
    ).order_by("-created_at")[:int(config.get("limit", 10))]
    return {
        "activity": [{
            "action": l.get_action_display(), "resource": l.resource_type,
            "at": l.created_at.isoformat(),
        } for l in logs],
    }


def w_dora(user, config):
    """Métricas DORA (reusa integrations.dora, mismo cálculo que /api/metrics/dora/).

    ``config.days`` (default 30, acotado a 1..365) define la ventana.
    """
    from apps.integrations.dora import get_dora_metrics
    try:
        days = int(config.get("days", 30))
    except (TypeError, ValueError):
        days = 30
    days = max(1, min(days, 365))
    return get_dora_metrics(user, days=days)


def w_audit_dashboard(user, config):
    """Dashboard de auditoría (reusa advanced_metrics.get_audit_dashboard)."""
    from apps.tasks.advanced_metrics import get_audit_dashboard
    return get_audit_dashboard(user)


WIDGET_TYPES = {
    "my_tasks": w_my_tasks,
    "overdue": w_overdue,
    "kpis": w_kpis,
    "blocked": w_blocked,
    "workload": w_workload,
    "velocity": w_velocity,
    "prs_open": w_prs_open,
    "upcoming_deadlines": w_upcoming_deadlines,
    "recent_activity": w_recent_activity,
    "dora": w_dora,
    "audit_dashboard": w_audit_dashboard,
}


def resolve_widget(user, widget):
    """Resuelve un widget a sus datos. Tipo desconocido → error amable."""
    fn = WIDGET_TYPES.get(widget.get("type"))
    if fn is None:
        return {"error": f"tipo de widget desconocido: {widget.get('type')}"}
    try:
        return fn(user, widget.get("config", {}))
    except Exception as e:  # noqa: BLE001 — un widget que falla no debe tumbar el dashboard
        return {"error": str(e)[:200]}
