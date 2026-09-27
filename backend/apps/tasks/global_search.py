"""Búsqueda global con sintaxis estilo GitHub/Jira.

Sintaxis soportada:
    assigned:me              tareas asignadas al usuario
    assigned:<email>         por email
    status:open|closed|<state>  open = no finalizada; closed = completada/cancelada
    tag:<nombre>             por etiqueta
    project:<nombre>         por proyecto (icontains)
    priority:p0..p5          por prioridad
    type:<task_type>         por tipo de tarea
    due:overdue|today|week   por fecha límite
    updated:<Nd>             actualizadas en los últimos N días (ej. updated:7d)
    "frase literal"          búsqueda de frase en título/descripción
    palabras sueltas         búsqueda de texto libre (todas deben coincidir)

Ejemplo: assigned:me status:open tag:backend updated:7d "problema login"
"""
import re
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from apps.projects.models import accessible_projects
from apps.tasks.models import Comment, Task
from apps.wiki.models import WikiPage

_TOKEN_RE = re.compile(r'(?P<field>\w+):(?P<value>"[^"]+"|\S+)|"(?P<phrase>[^"]+)"|(?P<word>\S+)')

_OPEN_STATES = ["backlog", "pending", "in_progress", "review", "blocked"]
_CLOSED_STATES = ["completed", "cancelled", "archived"]
_STATE_ALIASES = {
    "open": _OPEN_STATES,
    "closed": _CLOSED_STATES,
    "done": ["completed"],
}


def parse_query(q):
    """Parsea la query en filtros estructurados + texto libre."""
    filters = {}
    text_terms = []
    for m in _TOKEN_RE.finditer(q):
        field = m.group("field")
        if field:
            filters.setdefault(field.lower(), []).append(
                m.group("value").strip('"')
            )
        elif m.group("phrase"):
            text_terms.append(m.group("phrase"))
        elif m.group("word"):
            text_terms.append(m.group("word"))
    return filters, text_terms


def _apply_task_filters(qs, filters, user):
    """Aplica los filtros de sintaxis al queryset de tareas."""
    for assigned in filters.get("assigned", []):
        if assigned == "me":
            qs = qs.filter(assignee=user)
        else:
            qs = qs.filter(assignee__email__icontains=assigned)
    for st in filters.get("status", []):
        states = _STATE_ALIASES.get(st.lower(), [st])
        qs = qs.filter(state__in=states)
    for tag in filters.get("tag", []):
        qs = qs.filter(tags__name__iexact=tag)
    for proj in filters.get("project", []):
        qs = qs.filter(project__name__icontains=proj)
    for pri in filters.get("priority", []):
        m = re.match(r"p?(\d+)", pri.lower())
        if m:
            qs = qs.filter(priority=int(m.group(1)))
    for tt in filters.get("type", []):
        qs = qs.filter(task_type=tt)
    for due in filters.get("due", []):
        now = timezone.now()
        if due == "overdue":
            qs = qs.filter(due_date__lt=now)
        elif due == "today":
            today = now.replace(hour=0, minute=0, second=0)
            qs = qs.filter(due_date__gte=today,
                           due_date__lt=today + timedelta(days=1))
        elif due == "week":
            qs = qs.filter(due_date__lte=now + timedelta(days=7))
    for upd in filters.get("updated", []):
        m = re.match(r"(\d+)d", upd)
        if m:
            qs = qs.filter(updated_at__gte=timezone.now()
                           - timedelta(days=int(m.group(1))))
    return qs


def _text_q(terms, fields):
    """Q que exige que TODOS los términos aparezcan en algún campo."""
    q = Q()
    for term in terms:
        term_q = Q()
        for f in fields:
            term_q |= Q(**{f"{f}__icontains": term})
        q &= term_q
    return q


def global_search(user, query, limit=20):
    """Búsqueda global: tareas (con sintaxis), comentarios, wiki, proyectos.

    Los filtros de sintaxis solo aplican a tareas; el texto libre busca en
    todas las entidades accesibles.
    """
    filters, terms = parse_query(query)

    # --- Tareas: sintaxis completa + texto ---
    tasks_qs = Task.objects.for_user(user)
    tasks_qs = _apply_task_filters(tasks_qs, filters, user)
    if terms:
        tasks_qs = tasks_qs.filter(
            _text_q(terms, ["title", "description"]))
    tasks = [{
        "type": "task", "id": t.id, "title": t.title,
        "state": t.state, "priority": t.priority,
        "project": t.project.name if t.project else None,
        "updated_at": t.updated_at.isoformat(),
    } for t in tasks_qs.select_related("project")[:limit]]

    # --- Comentarios: texto libre en tareas accesibles ---
    comments = []
    if terms:
        accessible_tasks = Task.objects.for_user(user)
        for c in Comment.objects.filter(
            task__in=accessible_tasks
        ).filter(_text_q(terms, ["body"])).select_related(
            "task", "author")[:limit]:
            comments.append({
                "type": "comment", "id": c.id,
                "title": c.body[:120],
                "task": {"id": c.task_id, "title": c.task.title},
                "author": c.author.email if c.author else None,
            })

    # --- Wiki: texto libre ---
    wiki = []
    if terms:
        projects = accessible_projects(user)
        for w in WikiPage.objects.filter(
            Q(owner=user) | Q(project__in=projects)
        ).filter(_text_q(terms, ["title", "content"]))[:limit]:
            wiki.append({
                "type": "wiki", "id": w.id, "title": w.title,
                "project": w.project.name if w.project else None,
            })

    # --- Proyectos: texto libre ---
    projects_out = []
    if terms:
        for p in accessible_projects(user).filter(
            _text_q(terms, ["name", "description"]))[:limit]:
            projects_out.append({
                "type": "project", "id": p.id, "title": p.name,
                "is_archived": p.is_archived,
            })

    return {
        "query": query,
        "filters": filters,
        "tasks": tasks,
        "comments": comments,
        "wiki": wiki,
        "projects": projects_out,
    }
