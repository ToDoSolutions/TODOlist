"""Métricas avanzadas: Gantt, Burndown, Capacity, Audit dashboard."""
from django.utils import timezone
from django.db.models import Q, Count, Sum, Avg
from datetime import timedelta
from apps.tasks.models import Task, Sprint, TaskActivity
from apps.projects.models import Project


def get_gantt_data(user):
    """Datos para vista Gantt: tareas y sprints con fechas."""
    tasks = Task.objects.for_user(user).filter(
        Q(due_date__isnull=False) | Q(sprint__isnull=False)
    ).select_related("project", "sprint").order_by("due_date")[:100]

    return {
        "tasks": [
            {
                "id": t.id,
                "title": t.title,
                "project": t.project.name if t.project else None,
                "project_color": t.project.color if t.project else "#1976d2",
                "state": t.state,
                "start_date": t.start_date.isoformat() if t.start_date else (t.created_at.date().isoformat() if t.created_at else None),
                "due_date": t.due_date.isoformat() if t.due_date else None,
                "sprint": t.sprint.name if t.sprint else None,
                "story_points": t.story_points,
            }
            for t in tasks
        ],
        "sprints": [
            {
                "id": s.id,
                "name": s.name,
                "start_date": s.start_date.isoformat(),
                "end_date": s.end_date.isoformat(),
                "state": s.state,
            }
            for s in Sprint.objects.filter(owner=user).order_by("start_date")
        ],
    }


def get_burndown_data(user, sprint_id):
    """Datos para burndown chart de un sprint."""
    try:
        sprint = Sprint.objects.get(owner=user, id=sprint_id)
    except Sprint.DoesNotExist:
        return None

    tasks = Task.objects.filter(sprint=sprint, owner=user)
    total_points = tasks.aggregate(Sum("story_points"))["story_points__sum"] or 0
    total_tasks = tasks.count()

    # Ideal burndown: línea recta desde total_points hasta 0
    days = (sprint.end_date - sprint.start_date).days or 1
    ideal = []
    for d in range(days + 1):
        day = sprint.start_date + timedelta(days=d)
        remaining = total_points - (total_points * d / days)
        ideal.append({"date": day.isoformat(), "ideal": max(0, round(remaining, 1))})

    # Actual burndown: puntos restantes por día
    actual = []
    completed = tasks.filter(state="completed")
    for d in range(days + 1):
        day = sprint.start_date + timedelta(days=d)
        day_end = day + timedelta(days=1)
        completed_by_day = completed.filter(completed_at__date__lt=day_end)
        done_points = completed_by_day.aggregate(Sum("story_points"))["story_points__sum"] or 0
        remaining = total_points - done_points
        actual.append({"date": day.isoformat(), "remaining": max(0, remaining)})

    return {
        "sprint": {"name": sprint.name, "start_date": sprint.start_date.isoformat(), "end_date": sprint.end_date.isoformat()},
        "total_points": total_points,
        "total_tasks": total_tasks,
        "ideal": ideal,
        "actual": actual,
    }


def get_capacity_data(user):
    """Datos de capacity planning: carga por proyecto."""
    projects = Project.objects.filter(owner=user, is_archived=False)
    capacity = []
    for p in projects:
        tasks = Task.objects.filter(project=p, owner=user)
        open_tasks = tasks.exclude(state__in=["completed", "cancelled", "archived"])
        total_points = open_tasks.aggregate(Sum("story_points"))["story_points__sum"] or 0
        capacity.append({
            "project": p.name,
            "project_color": p.color,
            "open_tasks": open_tasks.count(),
            "total_points": total_points,
            "in_progress": open_tasks.filter(state="in_progress").count(),
            "blocked": open_tasks.filter(state="blocked").count(),
        })

    capacity.sort(key=lambda x: x["total_points"], reverse=True)
    return {"capacity": capacity}


def get_audit_dashboard(user):
    """Dashboard de auditoría con gráficos."""
    from apps.collaboration.models import AuditLog

    logs = AuditLog.objects.filter(actor=user)

    # Acciones por tipo
    by_action = {}
    for log in logs:
        by_action[log.action] = by_action.get(log.action, 0) + 1

    # Actividad por día (últimos 30 días)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    recent = logs.filter(created_at__gte=thirty_days_ago)
    by_day = {}
    for log in recent:
        day = log.created_at.date().isoformat()
        by_day[day] = by_day.get(day, 0) + 1

    # Recursos más afectados
    by_resource = {}
    for log in logs:
        by_resource[log.resource_type] = by_resource.get(log.resource_type, 0) + 1

    return {
        "total_actions": logs.count(),
        "by_action": by_action,
        "by_day": by_day,
        "by_resource": by_resource,
        "last_30_days": recent.count(),
    }
