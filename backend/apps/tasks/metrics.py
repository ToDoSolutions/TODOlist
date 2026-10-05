"""Motor de métricas y estadísticas del flujo de trabajo."""
from datetime import timedelta

from django.utils import timezone

from apps.tasks.models import Sprint, Task, TaskActivity


def _my_tasks(user):
    """Scope "mis tareas" coherente con my-work/productivity: owner o
    asignada (FK o M2M) dentro del conjunto visible para el usuario.
    Las tareas solo observadas o legibles por membresía no cuentan."""
    from django.db.models import Q

    return Task.objects.for_user(user).filter(
        Q(owner=user) | Q(assignee=user) | Q(assignees=user)
    ).distinct()


def _percentile(values, p):
    """Calcula el percentil p de una lista de valores."""
    if not values:
        return 0
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * (p / 100)
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def _hours_between(start, end):
    """Horas entre dos datetimes."""
    if not start or not end:
        return 0
    return (end - start).total_seconds() / 3600


def _days_between(start, end):
    """Días entre dos datetimes."""
    return _hours_between(start, end) / 24


def get_flow_metrics(user, days=30):
    """Calcula métricas de flujo: lead time, cycle time, throughput, WIP."""
    now = timezone.now()
    since = now - timedelta(days=days)

    tasks = _my_tasks(user)

    # Throughput: tareas completadas en el periodo
    completed_in_period = tasks.filter(
        completed_at__gte=since, completed_at__lte=now
    )
    throughput = completed_in_period.count()

    # Tareas creadas en el periodo
    created_in_period = tasks.filter(created_at__gte=since)
    created_count = created_in_period.count()

    # WIP actual: tareas en progreso
    wip = tasks.filter(state__in=["in_progress", "review", "blocked"]).count()

    # Backlog actual
    backlog = tasks.filter(state__in=["backlog", "pending"]).count()

    # Lead time: created_at → completed_at (para tareas completadas)
    lead_times_days = []
    for t in completed_in_period:
        if t.created_at and t.completed_at:
            lead_times_days.append(_days_between(t.created_at, t.completed_at))

    # Cycle time: primera vez en in_progress → completed_at
    cycle_times_days = []
    for t in completed_in_period:
        # Buscar la actividad de cambio a in_progress
        start_activity = t.activities.filter(
            action="state_changed", new_value="in_progress"
        ).order_by("created_at").first()
        if start_activity and t.completed_at:
            cycle_times_days.append(_days_between(start_activity.created_at, t.completed_at))

    # Tareas bloqueadas
    blocked = tasks.filter(state="blocked").count()

    # Tareas vencidas
    overdue = tasks.filter(
        due_date__lt=now,
        state__in=["pending", "in_progress", "review", "blocked"],
    ).count()

    return {
        "period_days": days,
        "throughput": throughput,
        "created": created_count,
        "wip": wip,
        "backlog": backlog,
        "blocked": blocked,
        "overdue": overdue,
        "lead_time": {
            "count": len(lead_times_days),
            "mean": round(sum(lead_times_days) / len(lead_times_days), 2) if lead_times_days else 0,
            "median": round(_percentile(lead_times_days, 50), 2),
            "p75": round(_percentile(lead_times_days, 75), 2),
            "p90": round(_percentile(lead_times_days, 90), 2),
            "p95": round(_percentile(lead_times_days, 95), 2),
            "min": round(min(lead_times_days), 2) if lead_times_days else 0,
            "max": round(max(lead_times_days), 2) if lead_times_days else 0,
        },
        "cycle_time": {
            "count": len(cycle_times_days),
            "mean": round(sum(cycle_times_days) / len(cycle_times_days), 2) if cycle_times_days else 0,
            "median": round(_percentile(cycle_times_days, 50), 2),
            "p75": round(_percentile(cycle_times_days, 75), 2),
            "p90": round(_percentile(cycle_times_days, 90), 2),
            "p95": round(_percentile(cycle_times_days, 95), 2),
            "min": round(min(cycle_times_days), 2) if cycle_times_days else 0,
            "max": round(max(cycle_times_days), 2) if cycle_times_days else 0,
        },
    }


def get_backlog_health(user):
    """Salud del backlog: tareas sin estimación, sin responsable, antiguas, etc."""
    now = timezone.now()
    tasks = _my_tasks(user)
    open_tasks = tasks.exclude(state__in=["completed", "cancelled", "archived"])

    # Tareas antiguas (> 30 días sin actividad)
    old_threshold = now - timedelta(days=30)
    old_tasks = open_tasks.filter(updated_at__lt=old_threshold).count()

    # Sin prioridad (P3 es la default, considerar sin prioridad si es P5)
    no_priority = open_tasks.filter(priority=5).count()

    # Sin estimación
    no_estimate = open_tasks.filter(
        story_points__isnull=True, estimate_hours__isnull=True, size=""
    ).count()

    # Sin fecha límite
    no_due_date = open_tasks.filter(due_date__isnull=True).count()

    # Reabiertas
    reopened = TaskActivity.objects.filter(
        task__in=tasks, action="reopened",
        created_at__gte=now - timedelta(days=30),
    ).count()

    # Edad promedio del backlog
    ages = []
    for t in open_tasks:
        if t.created_at:
            ages.append(_days_between(t.created_at, now))

    return {
        "total_open": open_tasks.count(),
        "old_tasks_30d": old_tasks,
        "no_priority": no_priority,
        "no_estimate": no_estimate,
        "no_due_date": no_due_date,
        "reopened_30d": reopened,
        "avg_age_days": round(sum(ages) / len(ages), 1) if ages else 0,
        "health_score": _calculate_health_score(
            open_tasks.count(), old_tasks, no_estimate, no_due_date, overdue=0
        ),
    }


def _calculate_health_score(total, old, no_est, no_due, overdue):
    """Score 0-100, mayor es mejor."""
    if total == 0:
        return 100
    score = 100
    score -= (old / total) * 30  # hasta -30 por tareas antiguas
    score -= (no_est / total) * 20  # hasta -20 sin estimación
    score -= (no_due / total) * 15  # hasta -15 sin fecha
    score -= (overdue / total) * 35  # hasta -35 vencidas
    return max(0, round(score, 1))


def get_sprint_metrics(user, sprint_id):
    """Métricas de un sprint específico."""
    try:
        from django.db.models import Q

        from apps.projects.models import accessible_projects
        sprint = Sprint.objects.get(
            Q(owner=user) | Q(project__in=accessible_projects(user)),
            id=sprint_id,
        )
    except Sprint.DoesNotExist:
        return None

    tasks = sprint.tasks.all()
    total = tasks.count()
    done = tasks.filter(state="completed").count()
    in_progress = tasks.filter(state__in=["in_progress", "review"]).count()
    blocked = tasks.filter(state="blocked").count()
    pending = tasks.filter(state__in=["pending", "backlog"]).count()

    # Story points
    sp_total = sum(t.story_points or 0 for t in tasks)
    sp_done = sum(t.story_points or 0 for t in tasks.filter(state="completed"))

    # Tareas añadidas después del inicio (scope creep)
    from datetime import datetime
    from datetime import time as dtime
    start_dt = timezone.make_aware(datetime.combine(sprint.start_date, dtime.min)) if sprint.start_date else None
    added_after_start = tasks.filter(created_at__gt=start_dt).count() if start_dt else 0

    return {
        "sprint_name": sprint.name,
        "sprint_state": sprint.state,
        "total_tasks": total,
        "done": done,
        "in_progress": in_progress,
        "blocked": blocked,
        "pending": pending,
        "story_points_total": sp_total,
        "story_points_done": sp_done,
        "progress_pct": round((done / total * 100) if total > 0 else 0, 1),
        "added_after_start": added_after_start,
        "scope_creep_pct": round((added_after_start / total * 100) if total > 0 else 0, 1),
    }


def get_dashboard_summary(user):
    """Dashboard general: resumen ejecutivo."""
    now = timezone.now()
    tasks = _my_tasks(user)

    open_count = tasks.exclude(state__in=["completed", "cancelled", "archived"]).count()
    completed_count = tasks.filter(state="completed").count()
    overdue = tasks.filter(
        due_date__lt=now,
        state__in=["pending", "in_progress", "review", "blocked"],
    ).count()
    blocked = tasks.filter(state="blocked").count()

    # Por estado
    by_state = {}
    for state, label in Task.State.choices:
        by_state[state] = tasks.filter(state=state).count()

    # Por prioridad
    by_priority = {}
    for p in range(6):
        by_priority[f"P{p}"] = tasks.filter(priority=p).count()

    # Por tipo
    by_type = {}
    for t, label in Task.Type.choices:
        by_type[t] = tasks.filter(task_type=t).count()

    # Tendencia del backlog (últimos 7 días)
    backlog_trend = []
    for i in range(7, -1, -1):
        day = now - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        created = tasks.filter(created_at__lt=day_start).count()
        completed = tasks.filter(completed_at__lt=day_start).count()
        backlog_trend.append({
            "date": day_start.strftime("%Y-%m-%d"),
            "backlog": created - completed,
        })

    # Sprint activo
    active_sprint = Sprint.objects.filter(
        owner=user, state=Sprint.SprintState.ACTIVE
    ).first()
    sprint_info = None
    if active_sprint:
        sprint_info = get_sprint_metrics(user, active_sprint.id)

    return {
        "open": open_count,
        "completed": completed_count,
        "overdue": overdue,
        "blocked": blocked,
        "by_state": by_state,
        "by_priority": by_priority,
        "by_type": by_type,
        "backlog_trend": backlog_trend,
        "active_sprint": sprint_info,
    }


def get_pr_metrics(user):
    """Métricas de pull requests sincronizados."""
    from apps.integrations.models import GitHubPullRequest

    prs = GitHubPullRequest.objects.filter(repo__installation__user=user)
    open_prs = prs.filter(state="open")
    merged_prs = prs.filter(is_merged=True)
    closed_prs = prs.filter(state="closed", is_merged=False)

    # PRs estancados (abiertos > 7 días sin merge)
    now = timezone.now()
    stale = open_prs.filter(
        created_at_gh__lt=now - timedelta(days=7)
    ).count()

    # Tiempo hasta fusión
    merge_times = []
    for pr in merged_prs:
        if pr.created_at_gh and pr.merged_at:
            merge_times.append(_days_between(pr.created_at_gh, pr.merged_at))

    # PRs con CI fallida
    ci_failed = open_prs.filter(ci_status="failure").count()

    return {
        "total": prs.count(),
        "open": open_prs.count(),
        "merged": merged_prs.count(),
        "closed_unmerged": closed_prs.count(),
        "stale_7d": stale,
        "ci_failed": ci_failed,
        "merge_time": {
            "count": len(merge_times),
            "mean": round(sum(merge_times) / len(merge_times), 2) if merge_times else 0,
            "median": round(_percentile(merge_times, 50), 2),
            "p90": round(_percentile(merge_times, 90), 2),
        },
    }
