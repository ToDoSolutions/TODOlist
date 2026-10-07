"""Conversión Task ⇄ VTODO (iCalendar RFC 5545 / CalDAV).

Los clientes CalDAV de tareas (Thunderbird, Tasks.org, Apple Reminders,
DAVx5+jtx…) hablan VTODO, no VEVENT. Aquí va el mapeo de campos.
"""
from __future__ import annotations

import contextlib
from datetime import UTC

from django.utils import timezone

PRODID = "-//TODOlist//CalDAV Tasks//ES"

# Task.state → VTODO STATUS
_STATE_TO_STATUS = {
    "completed": "COMPLETED",
    "cancelled": "CANCELLED",
    "in_progress": "IN-PROCESS",
    "review": "IN-PROCESS",
    "blocked": "IN-PROCESS",
}
# VTODO STATUS → Task.state
_STATUS_TO_STATE = {
    "COMPLETED": "completed",
    "CANCELLED": "cancelled",
    "IN-PROCESS": "in_progress",
    "NEEDS-ACTION": "pending",
}

# Priority P0–P5 ↔ RFC 5545 PRIORITY 1–9 (0 = undefined)
_PTO_V = {0: 1, 1: 3, 2: 4, 3: 5, 4: 7, 5: 9}
_V_TO_P = {1: 0, 2: 0, 3: 1, 4: 2, 5: 3, 6: 4, 7: 4, 8: 5, 9: 5}


def _esc(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(",", "\\,")
        .replace(";", "\\;")
        .replace("\n", "\\n")
    )


def _unesc(value: str) -> str:
    out, prev = [], False
    for ch in value:
        if prev:
            out.append({"n": "\n", "N": "\n"}.get(ch, ch))
            prev = False
        elif ch == "\\":
            prev = True
        else:
            out.append(ch)
    return "".join(out)


def task_to_vtodo(task) -> str:
    """Serializa una Task como VCALENDAR con un VTODO."""
    uid = f"task-{task.id}@todolist"
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODID}",
        "BEGIN:VTODO",
        f"UID:{uid}",
        f"DTSTAMP:{task.created_at.strftime('%Y%m%dT%H%M%SZ')}",
        f"LAST-MODIFIED:{task.updated_at.strftime('%Y%m%dT%H%M%SZ')}",
        f"SUMMARY:{_esc(task.title)}",
        f"STATUS:{_STATE_TO_STATUS.get(task.state, 'NEEDS-ACTION')}",
    ]
    if task.priority is not None:
        lines.append(f"PRIORITY:{_PTO_V.get(int(task.priority), 5)}")
    if task.description:
        lines.append(f"DESCRIPTION:{_esc(task.description)}")
    if task.due_date:
        due = task.due_date
        if timezone.is_naive(due):
            due = timezone.make_aware(due, UTC)
        lines.append(f"DUE:{due.strftime('%Y%m%dT%H%M%SZ')}")
    if task.state == "completed" and task.completed_at:
        comp = task.completed_at
        if timezone.is_naive(comp):
            comp = timezone.make_aware(comp, UTC)
        lines.append(f"COMPLETED:{comp.strftime('%Y%m%dT%H%M%SZ')}")
    lines += ["END:VTODO", "END:VCALENDAR"]
    return "\r\n".join(lines)


def _iter_props(text: str):
    """Itera propiedades iCal sencillas (unfolding + split en ':')."""
    # Unfolding RFC 5545: continuación = línea empezando con espacio/tab
    lines: list[str] = []
    for raw in text.replace("\r\n", "\n").split("\n"):
        if raw[:1] in (" ", "\t") and lines:
            lines[-1] += raw[1:]
        elif raw.strip():
            lines.append(raw)
    for line in lines:
        name, sep, value = line.partition(":")
        if not sep:
            continue
        prop = name.split(";")[0].strip().upper()
        yield prop, value.strip()


def _parse_dt(value: str):
    """DTYPE iCal ('20260115T120000Z' o '20260115') → datetime aware UTC."""
    from datetime import datetime

    if "T" in value:
        value, fmt = value.upper().rstrip("Z"), "%Y%m%dT%H%M%S"
    else:
        fmt = "%Y%m%d"
    try:
        return datetime.strptime(value, fmt).replace(tzinfo=UTC)
    except ValueError:
        return None


def vtodo_to_fields(ical_text: str) -> dict:
    """Parsea un VTODO → campos de Task {title, description, due_date,
    state, priority}. Keys ausentes no se tocan."""
    fields: dict = {}
    inside = False
    for prop, value in _iter_props(ical_text):
        if prop == "BEGIN" and value.upper() == "VTODO":
            inside = True
        elif prop == "END" and value.upper() == "VTODO":
            inside = False
        elif not inside:
            continue
        elif prop == "SUMMARY":
            fields["title"] = _unesc(value)
        elif prop == "DESCRIPTION":
            fields["description"] = _unesc(value)
        elif prop == "DUE" or prop == "DTSTART":
            if "due_date" not in fields:
                dt = _parse_dt(value)
                if dt:
                    fields["due_date"] = dt
        elif prop == "STATUS":
            state = _STATUS_TO_STATE.get(value.upper())
            if state:
                fields["state"] = state
        elif prop == "PRIORITY":
            with contextlib.suppress(ValueError):
                fields["priority"] = _V_TO_P.get(int(value), 3)
    return fields


def task_uid(task) -> str:
    return f"task-{task.id}@todolist"


def uid_to_task_id(uid: str) -> int | None:
    """'task-123@todolist' o 'task-123.ics' → 123."""
    import re

    m = re.match(r"task-(\d+)", uid or "")
    return int(m.group(1)) if m else None
