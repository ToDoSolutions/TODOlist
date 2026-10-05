"""Servicios heurísticos del asistente de IA.

Estas funciones no dependen de un modelo externo: usan reglas basadas en
fechas, prioridad, estado y dependencias para generar sugerencias útiles.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.db.models import Q
from django.utils import timezone

from apps.tasks.models import Task, TaskRelation

# Fibonacci-ish para story points
STORY_POINT_OPTIONS = [1, 2, 3, 5, 8, 13]


def _days_until_due(task: Task) -> float | None:
    """Días hasta el vencimiento. Negativo si está vencida. None si sin fecha."""
    if not task.due_date:
        return None
    delta = task.due_date - timezone.now()
    return delta.total_seconds() / 86400


def estimate_priority(task: Task) -> dict[str, Any]:
    """Heurística de prioridad basada en due_date, prioridad, estado y dependencias.

    Devuelve ``{"suggested_priority": int 0-5, "confidence": float 0-1}``.
    """
    score = 0.0
    reasons: list[str] = []

    # 1. Proximidad del due_date
    days = _days_until_due(task)
    if days is not None:
        if days < 0:
            score += 3.0
            reasons.append("tarea vencida")
        elif days <= 1:
            score += 2.5
            reasons.append("vence en menos de 1 día")
        elif days <= 3:
            score += 1.5
            reasons.append("vence en menos de 3 días")
        elif days <= 7:
            score += 0.5
            reasons.append("vence en menos de 7 días")

    # 2. Prioridad actual (más baja = más urgente en esta escala)
    # P0=0 (crítica) ... P5=5 (algún día)
    priority_urgency = max(0, (5 - task.priority) / 5.0)  # 0..1
    score += priority_urgency * 1.5
    if task.priority <= 1:
        reasons.append("prioridad crítica/muy alta")

    # 3. Estado: en progreso suma urgencia, completada/cancelada la elimina
    if task.state in (Task.State.COMPLETED, Task.State.CANCELLED, Task.State.ARCHIVED):
        return {"suggested_priority": 5, "confidence": 0.9, "reasons": ["tarea inactiva"]}

    if task.state == Task.State.IN_PROGRESS:
        score += 1.0
        reasons.append("en progreso")
    elif task.state == Task.State.BLOCKED:
        score += 2.0
        reasons.append("bloqueada")

    # 4. Dependencias: si bloquea a otras tareas, sube urgencia
    blocks_others = TaskRelation.objects.filter(
        source=task, relation_type=TaskRelation.RelationType.BLOCKS
    ).count()
    if blocks_others:
        score += min(blocks_others, 3) * 0.5
        reasons.append(f"bloquea a {blocks_others} tarea(s)")

    # Mapear score (0..~8) a prioridad 0-5 (mayor score = menor número = más urgente)
    if score >= 6:
        suggested = 0
    elif score >= 4.5:
        suggested = 1
    elif score >= 3:
        suggested = 2
    elif score >= 1.5:
        suggested = 3
    elif score >= 0.5:
        suggested = 4
    else:
        suggested = 5

    # Confianza: mayor cuando hay más señales
    confidence = min(0.5 + len(reasons) * 0.1, 0.95)

    return {
        "suggested_priority": suggested,
        "confidence": round(confidence, 2),
        "reasons": reasons,
        "current_priority": task.priority,
    }


def estimate_story_points(task: Task) -> dict[str, Any]:
    """Heurística de story points basada en descripción, subtareas y dependencias.

    Devuelve ``{"suggested_points": int, "confidence": float 0-1}``.
    """
    score = 0.0
    reasons: list[str] = []

    # 1. Longitud de la descripción
    desc_len = len(task.description or "")
    if desc_len == 0:
        score += 1.0
        reasons.append("sin descripción")
    elif desc_len < 100:
        score += 2.0
        reasons.append("descripción corta")
    elif desc_len < 500:
        score += 4.0
        reasons.append("descripción media")
    else:
        score += 6.0
        reasons.append("descripción extensa")

    # 2. Número de subtareas
    subtask_count = task.subtasks.count()
    if subtask_count == 0:
        score += 1.0
    elif subtask_count <= 3:
        score += 3.0
        reasons.append(f"{subtask_count} subtarea(s)")
    elif subtask_count <= 6:
        score += 5.0
        reasons.append(f"{subtask_count} subtareas")
    else:
        score += 8.0
        reasons.append(f"{subtask_count} subtareas (muchas)")

    # 3. Dependencias (tareas de las que depende)
    depends_on = TaskRelation.objects.filter(
        source=task, relation_type=TaskRelation.RelationType.DEPENDS_ON
    ).count()
    if depends_on:
        score += min(depends_on, 4) * 1.0
        reasons.append(f"depende de {depends_on} tarea(s)")

    # Mapear score a la secuencia Fibonacci-ish
    if score <= 2:
        suggested = 1
    elif score <= 4:
        suggested = 2
    elif score <= 6:
        suggested = 3
    elif score <= 9:
        suggested = 5
    elif score <= 12:
        suggested = 8
    else:
        suggested = 13

    confidence = min(0.4 + len(reasons) * 0.12, 0.9)

    return {
        "suggested_points": suggested,
        "confidence": round(confidence, 2),
        "reasons": reasons,
        "current_story_points": task.story_points,
    }


def detect_blockers(user) -> list[dict[str, Any]]:
    """Detecta posibles bloqueos para las tareas de un usuario.

    - Tareas en progreso sin actualización hace 7+ días.
    - Tareas bloqueadas por dependencias no resueltas.
    - Tareas vencidas que siguen pendientes.
    """
    now = timezone.now()
    stale_threshold = now - timedelta(days=7)
    blockers: list[dict[str, Any]] = []

    # Excluir tareas con EncryptedTask vinculada (E2E): la IA opera sobre
    # texto claro y no debe procesar contenido cifrado.
    tasks = Task.objects.for_user(user).filter(
        Q(owner=user) | Q(assignee=user) | Q(assignees=user)
    ).distinct().exclude(
        state__in=[Task.State.COMPLETED, Task.State.CANCELLED, Task.State.ARCHIVED]
    ).exclude(encrypted_data__isnull=False)

    # 1. En progreso sin actualizaciones recientes
    stale = tasks.filter(state=Task.State.IN_PROGRESS, updated_at__lte=stale_threshold)
    for t in stale:
        days_stale = (now - t.updated_at).days
        blockers.append({
            "task_id": t.id,
            "task_title": t.title,
            "blocker_type": "stale_in_progress",
            "detail": f"Sin actualizaciones hace {days_stale} días",
            "severity": "medium",
        })

    # 2. Dependencias no resueltas:
    #    - DEPENDS_ON: source depende de target (bloqueada = source)
    #    - BLOCKS: source bloquea a target (bloqueada = target)
    relations = TaskRelation.objects.filter(
        Q(source__in=tasks, relation_type=TaskRelation.RelationType.DEPENDS_ON)
        | Q(target__in=tasks, relation_type=TaskRelation.RelationType.BLOCKS),
    ).select_related("source", "target")
    for rel in relations:
        if rel.relation_type == TaskRelation.RelationType.BLOCKS:
            blocked, blocker = rel.target, rel.source
            verb = "Bloqueada por"
        else:
            blocked, blocker = rel.source, rel.target
            verb = "Depende de"
        if blocker.state not in (Task.State.COMPLETED, Task.State.CANCELLED):
            blockers.append({
                "task_id": blocked.id,
                "task_title": blocked.title,
                "blocker_type": "dependency_unresolved",
                "detail": (
                    f"{verb} '{blocker.title}' "
                    f"(estado: {blocker.get_state_display()})"
                ),
                "blocking_task_id": blocker.id,
                "blocking_task_title": blocker.title,
                "severity": "high",
            })

    # 3. Vencidas y pendientes
    overdue = tasks.filter(
        due_date__lt=now,
        state__in=[Task.State.PENDING, Task.State.BACKLOG, Task.State.IN_PROGRESS],
    )
    for t in overdue:
        if t.due_date is None:
            continue
        days_overdue = (now - t.due_date).days
        blockers.append({
            "task_id": t.id,
            "task_title": t.title,
            "blocker_type": "overdue",
            "detail": f"Vencida hace {days_overdue} día(s)",
            "severity": "high" if days_overdue > 3 else "medium",
        })

    return blockers


def _improve_description_llm(task: Task) -> dict[str, Any] | None:
    """Versión LLM (BYOK): devuelve sugerencias + descripción reescrita.
    None si el LLM no está configurado o falla."""
    from .llm import chat, llm_configured

    if not llm_configured():
        return None
    prompt = (
        f"Título: {task.title}\n"
        f"Estado: {task.state} | Prioridad: P{task.priority}\n"
        f"Descripción actual:\n{task.description or '(vacía)'}\n\n"
        "Devuelve SOLO JSON válido: "
        '{"improved_description": str, "suggestions": [str]}'
    )
    text = chat(
        "Eres un asistente que mejora descripciones de tareas. "
        "Reescribe la descripción con contexto, objetivo y criterios de "
        "aceptación claros. Responde en el idioma de la tarea.",
        prompt,
    )
    if not text:
        return None
    import json
    try:
        # tolerante: extraer el bloque JSON aunque el modelo lo envuelva
        start, end = text.index("{"), text.rindex("}") + 1
        data = json.loads(text[start:end])
        return {
            "improved_description": str(data.get("improved_description", "")),
            "suggestions": [str(s) for s in data.get("suggestions", [])],
            "confidence": 0.85,
            "source": "llm",
        }
    except (ValueError, TypeError):
        return None


def improve_description(task: Task) -> dict[str, Any]:
    """Sugiere mejoras a la descripción de una tarea.

    Devuelve ``{"suggestions": [str, ...], "confidence": float}``.
    Con LLM configurado (BYOK) incluye además ``improved_description``.
    """
    llm = _improve_description_llm(task)
    if llm is not None:
        return llm

    suggestions: list[str] = []
    desc = (task.description or "").strip()

    if not desc:
        suggestions.append("La tarea no tiene descripción. Añade contexto, objetivo y criterios de aceptación.")
        suggestions.append("Incluye pasos para reproducir o detalles de implementación esperados.")
    else:
        if len(desc) < 50:
            suggestions.append("La descripción es muy corta. Amplía el contexto y el resultado esperado.")
        if len(desc) < 200:
            suggestions.append("Considera añadir criterios de aceptación medibles.")

        # Palabras clave de contexto faltante
        lower = desc.lower()
        if "cómo" not in lower and "como" not in lower and "how" not in lower:
            suggestions.append("Describe cómo se debe realizar la tarea o los pasos involucrados.")
        if "por qué" not in lower and "por que" not in lower and "why" not in lower:
            suggestions.append("Explica por qué es necesaria esta tarea (motivación/impacto).")
        if "criterio" not in lower and "acceptance" not in lower and "definition" not in lower:
            suggestions.append("Añade criterios de aceptación o definición de 'hecho'.")

    # Subtareas como contexto
    if task.subtasks.exists() and not desc:
        suggestions.append("Tienes subtareas: referencia los pasos clave en la descripción principal.")

    # Dependencias
    depends_on = TaskRelation.objects.filter(
        source=task, relation_type=TaskRelation.RelationType.DEPENDS_ON
    ).exists()
    if depends_on:
        suggestions.append("La tarea tiene dependencias: menciónalas en la descripción para dar contexto.")

    if not suggestions:
        suggestions.append("La descripción parece completa. Revisa formato y claridad.")

    confidence = 0.6 if suggestions else 0.9
    return {
        "suggestions": suggestions,
        "confidence": round(confidence, 2),
        "source": "heuristic",
    }
