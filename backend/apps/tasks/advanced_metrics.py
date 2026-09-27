"""Métricas avanzadas: Gantt, Burndown, Capacity, Audit dashboard."""
from datetime import timedelta

from django.db.models import Q, Sum
from django.utils import timezone

from apps.projects.models import accessible_projects
from apps.tasks.models import Sprint, Task


def get_gantt_data(user):
    """Datos para vista Gantt: tareas, sprints y dependencias entre tareas."""
    tasks = list(
        Task.objects.for_user(user).filter(
            Q(due_date__isnull=False) | Q(sprint__isnull=False)
        ).select_related("project", "sprint").order_by("due_date")[:100]
    )
    task_ids = {t.id for t in tasks}

    # Dependencias visualizables en el Gantt (Task A bloquea/depende de Task B)
    from .models import TaskRelation
    relations = TaskRelation.objects.filter(
        source_id__in=task_ids, target_id__in=task_ids
    ).select_related("source", "target")

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
        "dependencies": [
            {
                "source": r.source_id,
                "target": r.target_id,
                "type": r.relation_type,
            }
            for r in relations
        ],
        "sprints": [
            {
                "id": s.id,
                "name": s.name,
                "start_date": s.start_date.isoformat(),
                "end_date": s.end_date.isoformat(),
                "state": s.state,
            }
            for s in Sprint.objects.filter(
                Q(owner=user)
                | Q(project__in=accessible_projects(user))
            ).order_by("start_date")
        ],
    }


def get_burndown_data(user, sprint_id):
    """Datos para burndown chart de un sprint."""
    try:
        from django.db.models import Q

        from apps.projects.models import accessible_projects
        sprint = Sprint.objects.get(
            Q(owner=user) | Q(project__in=accessible_projects(user)),
            id=sprint_id,
        )
    except Sprint.DoesNotExist:
        return None

    # Burndown: todas las tareas del sprint (incluye miembros del proyecto)
    tasks = Task.objects.filter(sprint=sprint)
    total_points = tasks.aggregate(Sum("story_points"))["story_points__sum"] or 0
    total_tasks = tasks.count()

    # Ideal burndown: línea recta desde total_points hasta 0
    days = (sprint.end_date - sprint.start_date).days or 1
    ideal = []
    for d in range(days + 1):
        day = sprint.start_date + timedelta(days=d)
        remaining = total_points - (total_points * d / days)
        ideal.append({"date": day.isoformat(), "ideal": max(0, round(remaining, 1))})

    # Actual burndown: puntos restantes por día.
    # Antes: una query por día (N+1). Ahora se cargan las completadas una
    # vez y se acumula en memoria.
    completed_points = [
        (t.completed_at.date(), t.story_points or 0)
        for t in tasks.filter(state="completed", completed_at__isnull=False)
        .only("completed_at", "story_points")
    ]
    actual = []
    for d in range(days + 1):
        day = sprint.start_date + timedelta(days=d)
        day_end = (day + timedelta(days=1))
        day_end = day_end.date() if hasattr(day_end, "date") else day_end
        done_points = sum(p for c, p in completed_points if c < day_end)
        actual.append({"date": day.isoformat(), "remaining": max(0, total_points - done_points)})

    return {
        "sprint": {"name": sprint.name, "start_date": sprint.start_date.isoformat(), "end_date": sprint.end_date.isoformat()},
        "total_points": total_points,
        "total_tasks": total_tasks,
        "ideal": ideal,
        "actual": actual,
    }


def get_burnup_data(user, sprint_id):
    """Datos para burnup chart: trabajo completado vs scope total.

    A diferencia del burndown (trabajo restante), el burnup muestra
    progreso acumulado y cambios de scope — útil para detectar scope
    creep durante el sprint.
    """
    try:
        from django.db.models import Q

        from apps.projects.models import accessible_projects
        sprint = Sprint.objects.get(
            Q(owner=user) | Q(project__in=accessible_projects(user)),
            id=sprint_id,
        )
    except Sprint.DoesNotExist:
        return None

    tasks = Task.objects.filter(sprint=sprint)
    total_points = tasks.aggregate(Sum("story_points"))["story_points__sum"] or 0

    # Puntos completados por fecha (acumulable)
    completed_points = [
        (t.completed_at.date(), t.story_points or 0)
        for t in tasks.filter(state="completed", completed_at__isnull=False)
        .only("completed_at", "story_points")
    ]
    # Scope: tareas añadidas al sprint por fecha (aprox con created_at)
    added_points = [
        (t.created_at.date(), t.story_points or 0)
        for t in tasks.only("created_at", "story_points")
    ]

    days = (sprint.end_date - sprint.start_date).days or 1
    series = []
    for d in range(days + 1):
        day = sprint.start_date + timedelta(days=d)
        day_end = day + timedelta(days=1)
        done = sum(p for c, p in completed_points if c < day_end)
        scope = sum(p for c, p in added_points if c < day_end)
        series.append({
            "date": day.isoformat(),
            "completed": done,
            "scope": scope,
        })

    return {
        "sprint": {
            "name": sprint.name,
            "start_date": sprint.start_date.isoformat(),
            "end_date": sprint.end_date.isoformat(),
        },
        "total_points": total_points,
        "series": series,
    }


def get_capacity_data(user):
    """Datos de capacity planning: carga por proyecto."""
    from apps.projects.models import accessible_projects
    projects = accessible_projects(user).filter(is_archived=False)
    capacity = []
    for p in projects:
        tasks = Task.objects.filter(project=p)
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


def get_roadmap_data(user):
    """Roadmap/Timeline view: épicas como barras de alto nivel.

    Cada épica muestra: rango temporal (primer start_date → último
    due_date de sus tareas), progreso y distribución de estados.
    Los sprints actúan como milestones verticales.
    """
    from .models import Epic

    epics = Epic.objects.filter(
        Q(owner=user) | Q(project__in=accessible_projects(user))
    ).prefetch_related("tasks").order_by("created_at")[:50]

    lanes = []
    for epic in epics:
        tasks = list(epic.tasks.all())
        total = len(tasks)
        done = sum(
            1 for t in tasks
            if t.state in (Task.State.COMPLETED, Task.State.CANCELLED)
        )
        starts = [t.start_date or t.created_at for t in tasks if t.start_date or t.created_at]
        dues = [t.due_date for t in tasks if t.due_date]
        # Preferir las fechas explícitas de la épica; si no, inferir de tareas
        start = epic.start_date.isoformat() if epic.start_date else (
            min(s.isoformat() for s in starts) if starts else None
        )
        end = epic.end_date.isoformat() if epic.end_date else (
            max(d.isoformat() for d in dues) if dues else None
        )
        lanes.append({
            "id": epic.id,
            "title": epic.title,
            "color": epic.color,
            "state": epic.state,
            "start": start,
            "end": end,
            "total": total,
            "done": done,
            "progress": round(done / total * 100, 1) if total else 0,
            "tasks": [
                {
                    "id": t.id,
                    "title": t.title,
                    "state": t.state,
                    "start": (t.start_date or t.created_at).isoformat()
                        if (t.start_date or t.created_at) else None,
                    "due": t.due_date.isoformat() if t.due_date else None,
                }
                for t in sorted(tasks, key=lambda x: x.id)[:40]
            ],
        })

    sprints = Sprint.objects.filter(
        Q(owner=user) | Q(project__in=accessible_projects(user))
    ).order_by("start_date")

    return {
        "epics": lanes,
        "milestones": [
            {
                "id": s.id,
                "name": s.name,
                "kind": "sprint",
                "start": s.start_date.isoformat(),
                "end": s.end_date.isoformat(),
                "state": s.state,
            }
            for s in sprints
        ]
        + [
            {
                "id": t.id,
                "name": t.title,
                "kind": "task",
                "start": t.due_date.isoformat(),
                "end": t.due_date.isoformat(),
                "state": t.state,
            }
            for t in Task.objects.for_user(user).filter(
                is_milestone=True, due_date__isnull=False
            )[:50]
        ],
    }


def get_velocity_data(user):
    """Velocity histórica: puntos completados por sprint y estimado vs real.

    - velocity: story points completados en cada sprint cerrado/activo.
    - estimated_vs_actual: horas estimadas vs tiempo registrado (TimeEntry)
      por tarea completada, agregado por sprint.
    """
    from .models import TimeEntry

    sprints = Sprint.objects.filter(
        Q(owner=user) | Q(project__in=accessible_projects(user))
    ).order_by("start_date")[:20]

    velocity = []
    estimated_vs_actual = []
    for s in sprints:
        tasks = Task.objects.filter(sprint=s)
        done = tasks.filter(state="completed")
        done_points = done.aggregate(Sum("story_points"))["story_points__sum"] or 0
        velocity.append({
            "sprint": s.name,
            "state": s.state,
            "completed_points": done_points,
            "completed_tasks": done.count(),
        })
        estimated = done.aggregate(Sum("estimate_hours"))["estimate_hours__sum"] or 0
        actual_seconds = TimeEntry.objects.filter(task__in=done).aggregate(
            Sum("duration_seconds")
        )["duration_seconds__sum"] or 0
        estimated_vs_actual.append({
            "sprint": s.name,
            "estimated_hours": round(float(estimated), 2),
            "actual_hours": round(actual_seconds / 3600, 2),
        })

    return {"velocity": velocity, "estimated_vs_actual": estimated_vs_actual}


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


def get_workload_data(user):
    """Workload Management: carga de trabajo por miembro.

    Por cada persona con tareas abiertas (owner o assignee de tareas
    accesibles): horas estimadas pendientes, % de utilización frente a
    su capacidad semanal configurable (``weekly_capacity_hours``, 40h
    por defecto) y flag de sobreasignación (>100%).
    """
    projects = accessible_projects(user).filter(is_archived=False)
    open_tasks = Task.objects.exclude(
        state__in=["completed", "cancelled", "archived"]
    ).filter(Q(owner=user) | Q(project__in=projects))

    soon = timezone.now() + timedelta(days=7)
    members = {}
    for t in open_tasks.select_related("assignee", "owner"):
        for person in (t.assignee, t.owner):
            if person is None:
                continue
            m = members.setdefault(person.id, {
                "user_id": person.id,
                "email": person.email,
                "open_tasks": 0,
                "estimate_hours": 0.0,
                "story_points": 0,
                "in_progress": 0,
                "due_soon": 0,
                "capacity_hours": float(
                    getattr(person, "weekly_capacity_hours", None) or 40
                ),
            })
            m["open_tasks"] += 1
            if t.estimate_hours:
                m["estimate_hours"] += float(t.estimate_hours)
            if t.story_points:
                m["story_points"] += t.story_points
            if t.state == "in_progress":
                m["in_progress"] += 1
            if t.due_date and t.due_date <= soon:
                m["due_soon"] += 1

    for m in members.values():
        capacity = m["capacity_hours"] or 40.0
        m["utilization"] = round(
            m["estimate_hours"] / capacity * 100
        )
        m["over_allocated"] = m["utilization"] > 100

    return sorted(members.values(), key=lambda m: m["utilization"], reverse=True)
