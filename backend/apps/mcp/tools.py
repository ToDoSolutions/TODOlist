"""Tools MCP: capa fina sobre los serializers/querysets REST existentes.

Cada tool declara su JSON Schema de input y el scope de API key que exige
("read" o "write"). Los handlers reciben ``request`` (DRF, ya autenticado)
y devuelven datos serializables a JSON — el view los envuelve en el
envelope MCP ``{content: [{type: "text", text: ...}]}``.
"""
import json

from django.db.models import Max


def _task_brief(t):
    return {
        "id": t.id,
        "title": t.title,
        "state": t.state,
        "priority": t.priority,
        "due_date": t.due_date.isoformat() if t.due_date else None,
        "project_id": t.project_id,
        "assignee_id": t.assignee_id,
        "tags": [tag.name for tag in t.tags.all()],
    }


# ---------------------------------------------------------------- read tools


def tasks_list(request, args):
    from apps.tasks.models import Task

    qs = (
        Task.objects.for_user(request.user)
        .exclude(state=Task.State.ARCHIVED)
        .select_related("project", "assignee")
        .prefetch_related("tags")
        .order_by("-updated_at")
    )
    if args.get("project_id"):
        # Multi-homing: el filtro incluye hogares extra, igual que
        # ?project= en la REST API
        from django.db.models import Q
        pid = args["project_id"]
        qs = qs.filter(Q(project_id=pid) | Q(extra_projects=pid)).distinct()
    if args.get("state"):
        qs = qs.filter(state=args["state"])
    if args.get("q"):
        qs = qs.filter(title__icontains=args["q"])
    limit = min(int(args.get("limit") or 50), 200)
    return {"tasks": [_task_brief(t) for t in qs[:limit]]}


def tasks_get(request, args):
    from apps.tasks.models import Task
    from apps.tasks.serializers import TaskSerializer

    task = Task.objects.for_user(request.user).get(id=args["id"])
    return TaskSerializer(task, context={"request": request}).data


def tasks_search(request, args):
    from apps.tasks.global_search import global_search

    q = args.get("q", "")
    if not q.strip():
        return {"error": "q es requerido"}
    return global_search(request.user, q)


def projects_list(request, args):
    from apps.projects.models import accessible_projects

    qs = accessible_projects(request.user).filter(is_archived=False)
    return {
        "projects": [
            {"id": p.id, "name": p.name, "description": p.description}
            for p in qs.order_by("name")[:200]
        ]
    }


# ---------------------------------------------------------------- write tools


def _task_payload(args):
    """Normaliza los args MCP al contract del serializer REST:
    el schema expone ``project_id`` y el campo del serializer es ``project``."""
    data = dict(args)
    if "project_id" in data:
        data["project"] = data.pop("project_id")
    return data


def tasks_create(request, args):
    from apps.tasks.models import Task
    from apps.tasks.serializers import TaskCreateUpdateSerializer

    serializer = TaskCreateUpdateSerializer(
        data=_task_payload(args), context={"request": request}
    )
    serializer.is_valid(raise_exception=True)
    # Mismo contract que TaskViewSet.perform_create: owner + position +
    # seq por proyecto (ref legible "MP-12").
    next_pos = (
        Task.objects.for_user(request.user).aggregate(m=Max("position"))["m"]
        or 0
    ) + 1
    project = serializer.validated_data.get("project")
    seq = 0
    if project is not None:
        seq = (
            Task.objects.filter(project=project).aggregate(m=Max("seq"))["m"]
            or 0
        ) + 1
    task = serializer.save(
        owner=request.user, position=next_pos, seq=seq
    )
    return {"id": task.id, "title": task.title, "state": task.state}


def tasks_update(request, args):
    from apps.tasks.serializers import TaskCreateUpdateSerializer
    from apps.tasks.services import apply_completion_effects, get_editable_task

    task = get_editable_task(request.user, args["id"])
    if task is None:
        raise ValueError("Tarea no encontrada o sin permiso de edición")
    data = _task_payload({k: v for k, v in args.items() if k != "id"})
    serializer = TaskCreateUpdateSerializer(
        task, data=data, partial=True, context={"request": request}
    )
    serializer.is_valid(raise_exception=True)
    task = serializer.save()
    # Mismo post-update que TaskViewSet.perform_update.
    apply_completion_effects(task)
    return {"id": task.id, "title": task.title, "state": task.state}


def tasks_complete(request, args):
    from apps.tasks.models import Task
    from apps.tasks.services import apply_completion_effects, get_editable_task

    task = get_editable_task(request.user, args["id"])
    if task is None:
        raise ValueError("Tarea no encontrada o sin permiso de edición")
    task.state = Task.State.COMPLETED
    task.save(update_fields=["state", "updated_at"])
    # completed_at + siguiente ocurrencia de recurrentes.
    apply_completion_effects(task)
    return {"id": task.id, "state": task.state}


def comments_add(request, args):
    from apps.tasks.models import Comment, Task
    from apps.tasks.serializers import CommentSerializer

    # Paridad con REST (TaskViewSet.comments → get_object → POST exige
    # write): comentar requiere permiso de escritura sobre la tarea.
    task = Task.objects.for_user(request.user, write=True).filter(
        id=args["task_id"]
    ).first()
    if task is None:
        raise ValueError("Tarea no encontrada")
    comment = Comment.objects.create(
        task=task, author=request.user, body=args["text"]
    )
    return CommentSerializer(comment).data


# ---------------------------------------------------------------- registry

# name → {schema, scope, handler}
TOOLS = {
    "tasks_list": {
        "scope": "read",
        "description": "Lista tareas accesibles (filtros: project_id, state, q, limit≤200).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer"},
                "state": {
                    "type": "string",
                    "enum": [
                        "backlog", "pending", "in_progress", "blocked",
                        "review", "completed", "cancelled", "archived",
                    ],
                },
                "q": {"type": "string"},
                "limit": {"type": "integer", "default": 50},
            },
        },
        "handler": tasks_list,
    },
    "tasks_get": {
        "scope": "read",
        "description": "Detalle completo de una tarea por id.",
        "inputSchema": {
            "type": "object",
            "properties": {"id": {"type": "integer"}},
            "required": ["id"],
        },
        "handler": tasks_get,
    },
    "tasks_search": {
        "scope": "read",
        "description": (
            "Búsqueda global con sintaxis: assigned:me, status:open/closed, "
            "tag:, project:, priority:, type:, due:overdue|today|week, "
            'updated:Nd, "frase literal".'
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"q": {"type": "string"}},
            "required": ["q"],
        },
        "handler": tasks_search,
    },
    "projects_list": {
        "scope": "read",
        "description": "Lista proyectos accesibles del usuario.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": projects_list,
    },
    "tasks_create": {
        "scope": "write",
        "description": (
            "Crea una tarea. due_date ISO 8601; priority 0-5 "
            "(0=crítica, 3=media, 5=algún día)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "description": {"type": "string"},
                "priority": {"type": "integer", "minimum": 0, "maximum": 5},
                "state": {"type": "string"},
                "due_date": {"type": "string"},
                "project_id": {"type": "integer"},
            },
            "required": ["title"],
        },
        "handler": tasks_create,
    },
    "tasks_update": {
        "scope": "write",
        "description": "Actualiza campos de una tarea (parcial).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "title": {"type": "string"},
                "description": {"type": "string"},
                "priority": {"type": "integer", "minimum": 0, "maximum": 5},
                "state": {"type": "string"},
                "due_date": {"type": "string"},
                "project_id": {"type": "integer"},
            },
            "required": ["id"],
        },
        "handler": tasks_update,
    },
    "tasks_complete": {
        "scope": "write",
        "description": (
            "Marca una tarea como completada (aplica completed_at y "
            "siguiente ocurrencia si es recurrente)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"id": {"type": "integer"}},
            "required": ["id"],
        },
        "handler": tasks_complete,
    },
    "comments_add": {
        "scope": "write",
        "description": "Añade un comentario a una tarea.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer"},
                "text": {"type": "string"},
            },
            "required": ["task_id", "text"],
        },
        "handler": comments_add,
    },
}


def list_tools():
    return [
        {
            "name": name,
            "description": spec["description"],
            "inputSchema": spec["inputSchema"],
        }
        for name, spec in TOOLS.items()
    ]


def call_tool(request, name, args):
    """Ejecuta un tool. Devuelve (result_dict, None) o (None, error_str)."""
    spec = TOOLS.get(name)
    if spec is None:
        return None, f"Unknown tool: {name}"
    # Scopes por tool (equivalente a APIKeyScopePermission pero por tool,
    # porque todo llega por POST): "write" implica "read", "admin" ambos.
    from apps.users.api_auth import has_scope
    from apps.users.models import APIKey

    api_key = getattr(request, "auth", None)
    if isinstance(api_key, APIKey) and not (
        has_scope(api_key, spec["scope"])
        or (spec["scope"] == "read" and has_scope(api_key, "write"))
    ):
        return None, f"API key sin scope '{spec['scope']}'"
    try:
        result = spec["handler"](request, args or {})
    except Exception as e:  # noqa: BLE001  # boundary MCP: error → isError
        return None, str(e)
    return result, None


def tool_result_payload(result, error):
    """Envelope MCP de un tools/call."""
    if error is not None:
        return {
            "content": [{"type": "text", "text": error}],
            "isError": True,
        }
    return {
        "content": [
            {"type": "text", "text": json.dumps(result, default=str)}
        ],
        "isError": False,
    }
