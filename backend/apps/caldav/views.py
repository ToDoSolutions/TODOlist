"""Servidor CalDAV mínimo (RFC 4791/5545) sobre Task → VTODO.

Auth: HTTP Basic — el *password* es el token opaco de calendario del
usuario (`User.ical_token`, el mismo que el feed .ics; se genera y rota
en POST/DELETE /api/users/me/calendar_token/). El username es libre:
el token ya identifica al usuario. También acepta ``?token=``.

Rutas (todas bajo /api/caldav/):
    /api/caldav/                principal (OPTIONS, PROPFIND)
    /api/caldav/tasks/          colección (OPTIONS, PROPFIND, REPORT)
    /api/caldav/tasks/<uid>.ics objeto (GET, PUT, DELETE, OPTIONS)

Limitaciones deliberadas v1: el REPORT calendar-query ignora los filtros
time-range/comp (devuelve todas las tareas abiertas; los clientes filtran
localmente). Sin MKCALENDAR: una sola colección "tasks" por usuario.
"""
import re
from xml.sax.saxutils import escape

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from apps.tasks.models import Task

from .ical import task_to_vtodo, task_uid, uid_to_task_id, vtodo_to_fields

DAV_XMLNS = 'xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav"'
BASE = "/api/caldav"
COLLECTION = f"{BASE}/tasks/"


def _unauth():
    r = HttpResponse(status=401)
    r["WWW-Authenticate"] = 'Basic realm="TODOlist CalDAV"'
    return r


def _user_from_request(request):
    """ical_token vía Basic password o ?token=."""
    import base64

    auth = request.META.get("HTTP_AUTHORIZATION", "")
    token = ""
    if auth.lower().startswith("basic "):
        try:
            decoded = base64.b64decode(auth[6:]).decode("utf-8", "replace")
            token = decoded.split(":", 1)[-1]
        except Exception:  # noqa: BLE001
            token = ""
    if not token:
        token = request.GET.get("token", "")
    if not token:
        return None
    return get_user_model().objects.filter(
        ical_token=token, is_active=True
    ).first()


def _options():
    r = HttpResponse(status=204)
    r["DAV"] = "1, 3, calendar-access"
    r["Allow"] = "OPTIONS, PROPFIND, REPORT, GET, PUT, DELETE"
    return r


def _xml(body: str, status=207):
    return HttpResponse(
        f'<?xml version="1.0" encoding="utf-8"?>\n{body}',
        content_type='application/xml; charset=utf-8',
        status=status,
    )


def _etag(task) -> str:
    return f'"{task.id}-{task.version}"'


def _href(task) -> str:
    return f"{COLLECTION}{task_uid(task)}.ics"


def _task_responses(tasks):
    out = []
    for t in tasks:
        out.append(
            "<D:response>"
            f"<D:href>{escape(_href(t))}</D:href>"
            "<D:propstat><D:prop>"
            f"<D:getetag>{_etag(t)}</D:getetag>"
            "<D:getcontenttype>text/calendar; component=vtodo</D:getcontenttype>"
            "</D:prop><D:status>HTTP/1.1 200 OK</D:status></D:propstat>"
            "</D:response>"
        )
    return "".join(out)


def _open_tasks(user):
    return (
        Task.objects.for_user(user)
        .exclude(state__in=[Task.State.CANCELLED, Task.State.ARCHIVED])
        .order_by("id")[:2000]
    )


@csrf_exempt
def caldav_root(request):
    """Principal: OPTIONS + PROPFIND (discovery)."""
    if request.method == "OPTIONS":
        return _options()
    user = _user_from_request(request)
    if user is None:
        return _unauth()
    if request.method == "PROPFIND":
        return _xml(
            f'<D:multistatus {DAV_XMLNS}><D:response>'
            f"<D:href>{BASE}/</D:href>"
            "<D:propstat><D:prop>"
            "<D:resourcetype><D:principal/></D:resourcetype>"
            f"<D:displayname>{escape(user.email or user.username)}</D:displayname>"
            f"<D:current-user-principal><D:href>{BASE}/</D:href>"
            "</D:current-user-principal>"
            f"<C:calendar-home-set><D:href>{COLLECTION}</D:href>"
            "</C:calendar-home-set>"
            "</D:prop><D:status>HTTP/1.1 200 OK</D:status></D:propstat>"
            "</D:response></D:multistatus>"
        )
    return HttpResponse(status=405)


@csrf_exempt
def caldav_collection(request):
    """Colección 'tasks': OPTIONS + PROPFIND + REPORT."""
    if request.method == "OPTIONS":
        return _options()
    user = _user_from_request(request)
    if user is None:
        return _unauth()

    if request.method == "PROPFIND":
        depth = request.META.get("HTTP_DEPTH", "1")
        props = (
            "<D:propstat><D:prop>"
            "<D:resourcetype><D:collection/><C:calendar/></D:resourcetype>"
            "<D:displayname>TODOlist Tasks</D:displayname>"
            '<C:supported-calendar-component-set>'
            '<C:comp name="VTODO"/>'
            "</C:supported-calendar-component-set>"
            "<D:getcontenttype>text/calendar</D:getcontenttype>"
            "</D:prop><D:status>HTTP/1.1 200 OK</D:status></D:propstat>"
        )
        members = (
            _task_responses(_open_tasks(user)) if depth != "0" else ""
        )
        return _xml(
            f'<D:multistatus {DAV_XMLNS}><D:response>'
            f"<D:href>{COLLECTION}</D:href>{props}</D:response>"
            f"{members}</D:multistatus>"
        )

    if request.method == "REPORT":
        # calendar-multiget: hrefs concretos; calendar-query: todas.
        body = request.body.decode("utf-8", "replace")
        hrefs = re.findall(
            r"<(?:\w+:)?href[^>]*>([^<]+)</(?:\w+:)?href>", body
        )
        tasks = _open_tasks(user)
        if hrefs:
            wanted = {
                uid_to_task_id(h.rsplit("/", 1)[-1]) for h in hrefs
            }
            wanted.discard(None)
            tasks = [t for t in tasks if t.id in wanted]
        responses = "".join(
            "<D:response>"
            f"<D:href>{escape(_href(t))}</D:href>"
            "<D:propstat><D:prop>"
            f"<D:getetag>{_etag(t)}</D:getetag>"
            f"<C:calendar-data>{escape(task_to_vtodo(t))}</C:calendar-data>"
            "</D:prop><D:status>HTTP/1.1 200 OK</D:status></D:propstat>"
            "</D:response>"
            for t in tasks
        )
        return _xml(
            f'<D:multistatus {DAV_XMLNS}>{responses}</D:multistatus>'
        )

    return HttpResponse(status=405)


@csrf_exempt
def caldav_object(request, name):
    """Objeto VTODO: GET / PUT / DELETE."""
    if request.method == "OPTIONS":
        return _options()
    user = _user_from_request(request)
    if user is None:
        return _unauth()

    # name = "task-42@todolist.ics" o el uid que mande el cliente
    uid = name.removesuffix(".ics")
    task = None
    task_id = uid_to_task_id(uid)
    if task_id:
        task = Task.objects.for_user(user, write=True).filter(
            id=task_id
        ).first()
    if task is None:
        task = Task.objects.for_user(user, write=True).filter(
            caldav_uid=uid
        ).first()

    if request.method == "GET":
        if task is None:
            return HttpResponse(status=404)
        r = HttpResponse(
            task_to_vtodo(task),
            content_type="text/calendar; charset=utf-8",
        )
        r["ETag"] = _etag(task)
        return r

    if request.method == "PUT":
        fields = vtodo_to_fields(request.body.decode("utf-8", "replace"))
        if task is None and not fields.get("title"):
            return HttpResponse(status=400)
        if task is None:
            # crear: uid del cliente queda registrado para round-trip;
            # posición + seq por el canal estándar (la tarea lleva ref)
            from apps.tasks.services import next_position_seq
            pos, seq = next_position_seq(user)
            task = Task.objects.create(
                owner=user,
                title=fields.pop("title"),
                caldav_uid=uid,
                position=pos,
                seq=seq,
                **fields,
            )
            r = HttpResponse(status=201)
        else:
            # Paridad con REST/offline sync: un PUT que cambia STATUS
            # debe respetar el workflow del proyecto — antes CalDAV
            # saltaba la validación entera.
            if "state" in fields:
                from apps.tasks.services import assert_state_transition
                try:
                    assert_state_transition(task, fields["state"])
                except ValueError as e:
                    return HttpResponse(str(e), status=403)
            for k, v in fields.items():
                setattr(task, k, v)
            task.caldav_uid = task.caldav_uid or uid
            task.save()
            r = HttpResponse(status=204)
        # completed_at + recurrencia por el canal estándar
        from apps.tasks.services import apply_completion_effects

        apply_completion_effects(task)
        r["ETag"] = _etag(task)
        r["Location"] = _href(task)
        return r

    if request.method == "DELETE":
        if task is None:
            return HttpResponse(status=404)
        task.delete()
        return HttpResponse(status=204)

    return HttpResponse(status=405)
