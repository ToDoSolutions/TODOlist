"""Servicios heurísticos del asistente de IA.

Estas funciones no dependen de un modelo externo: usan reglas basadas en
fechas, prioridad, estado y dependencias para generar sugerencias útiles.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List

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


def estimate_priority(task: Task) -> Dict[str, Any]:
    """Heurística de prioridad basada en due_date, prioridad, estado y dependencias.

    Devuelve ``{"suggested_priority": int 0-5, "confidence": float 0-1}``.
    """
    score = 0.0
    reasons: List[str] = []

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


def estimate_story_points(task: Task) -> Dict[str, Any]:
    """Heurística de story points basada en descripción, subtareas y dependencias.

    Devuelve ``{"suggested_points": int, "confidence": float 0-1}``.
    """
    score = 0.0
    reasons: List[str] = []

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


def detect_blockers(user) -> List[Dict[str, Any]]:
    """Detecta posibles bloqueos para las tareas de un usuario.

    - Tareas en progreso sin actualización hace 7+ días.
    - Tareas bloqueadas por dependencias no resueltas.
    - Tareas vencidas que siguen pendientes.
    """
    now = timezone.now()
    stale_threshold = now - timedelta(days=7)
    blockers: List[Dict[str, Any]] = []

    tasks = Task.objects.filter(owner=user).exclude(
        state__in=[Task.State.COMPLETED, Task.State.CANCELLED, Task.State.ARCHIVED]
    )

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

    # 2. Dependencias no resueltas (depends_on / blocked)
    relations = TaskRelation.objects.filter(
        source__in=tasks,
        relation_type__in=[
            TaskRelation.RelationType.DEPENDS_ON,
            TaskRelation.RelationType.BLOCKS,
        ],
    ).select_related("target")
    for rel in relations:
        target = rel.target
        if target.state not in (Task.State.COMPLETED, Task.State.CANCELLED):
            blockers.append({
                "task_id": rel.source_id,
                "task_title": rel.source.title,
                "blocker_type": "dependency_unresolved",
                "detail": f"Depende de '{target.title}' (estado: {target.state})",
                "blocking_task_id": target.id,
                "blocking_task_title": target.title,
                "severity": "high",
            })

    # 3. Vencidas y pendientes
    overdue = tasks.filter(
        due_date__lt=now,
        state__in=[Task.State.PENDING, Task.State.BACKLOG, Task.State.IN_PROGRESS],
    )
    for t in overdue:
        days_overdue = (now - t.due_date).days
        blockers.append({
            "task_id": t.id,
            "task_title": t.title,
            "blocker_type": "overdue",
            "detail": f"Vencida hace {days_overdue} día(s)",
            "severity": "high" if days_overdue > 3 else "medium",
        })

    return blockers


def improve_description(task: Task) -> Dict[str, Any]:
    """Sugiere mejoras a la descripción de una tarea.

    Devuelve ``{"suggestions": [str, ...], "confidence": float}``.
    """
    suggestions: List[str] = []
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
    return {"suggestions": suggestions, "confidence": round(confidence, 2)}
