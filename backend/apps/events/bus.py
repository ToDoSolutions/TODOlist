"""Bus de eventos de dominio sobre el OutboxEvent.


`publish()` persiste el evento en la transacción del caller (atómico con el
cambio de negocio) y lo despacha de inmediato a los handlers registrados —
misma semántica temporal que los signals actuales. La diferencia: si un
handler falla, el evento queda FAILED y `process_pending_events` lo
reintenta (los handlers deben ser idempotentes).

Limitación conocida (audit B-02): el despacho es síncrono — los handlers
de efectos externos (webhook HTTP, WS push) corren dentro del request
que provocó el evento, con los timeouts acotados de cada cliente
(requests: 10 s). Moverlos tras commit (``on_commit``) o a Celery es
deuda deliberada: los tests y el contrato asumen despacho inmediato.

Los efectos internos (TaskActivity, AuditLog, Notification, AutomationLog)
NO pasan por aquí: se escriben en la transacción del cambio vía signals.
"""
import logging
from collections.abc import Callable
from typing import Any

from django.db import transaction
from django.utils import timezone

from .models import OutboxEvent

logger = logging.getLogger(__name__)

# event_type → [handler(event)]
_HANDLERS: dict[str, list[Callable[..., Any]]] = {}

MAX_ATTEMPTS = 5


def register_handler(event_type):
    def deco(fn):
        _HANDLERS.setdefault(event_type, []).append(fn)
        return fn
    return deco


def publish(event_type, payload=None, idempotency_key=None):
    """Persiste el evento en la transacción actual y lo despacha ahora.

    Devuelve el evento (o None si ya existía la idempotency_key).
    """
    if idempotency_key:
        existing = OutboxEvent.objects.filter(
            idempotency_key=idempotency_key
        ).first()
        if existing:
            return existing
    event = OutboxEvent.objects.create(
        event_type=event_type,
        payload=payload or {},
        idempotency_key=idempotency_key,
    )
    dispatch(event)
    return event


def dispatch(event):
    """Ejecuta los handlers del evento. Fallos → FAILED (reintentable)."""
    handlers = _HANDLERS.get(event.event_type, [])
    errors = []
    for handler in handlers:
        try:
            handler(event)
        except Exception as exc:  # un handler no debe tumbar a los demás
            logger.exception(
                "Handler %s falló para evento %s",
                handler.__name__, event.event_type,
            )
            errors.append(f"{handler.__name__}: {exc}")
    event.attempts += 1
    if errors:
        event.status = OutboxEvent.Status.FAILED
        event.last_error = "; ".join(errors)[:2000]
    else:
        event.status = OutboxEvent.Status.PROCESSED
        event.processed_at = timezone.now()
        event.last_error = ""
    event.save(update_fields=["status", "attempts", "last_error", "processed_at"])
    return event.status == OutboxEvent.Status.PROCESSED


def process_pending_events(limit=200):
    """Reintenta eventos FAILED/PENDING (invocado por el beat de Celery).

    Cada evento se despacha bajo ``select_for_update(skip_locked)`` para
    que dos workers no procesen el mismo evento a la vez (en SQLite el
    lock es no-op, pero los handlers son idempotentes de todas formas).
    """
    pending_ids = list(
        OutboxEvent.objects.filter(
            status__in=[OutboxEvent.Status.PENDING, OutboxEvent.Status.FAILED],
            attempts__lt=MAX_ATTEMPTS,
        )
        .order_by("created_at")
        .values_list("id", flat=True)[:limit]
    )
    ok = failed = 0
    for event_id in pending_ids:
        with transaction.atomic():
            event = (
                OutboxEvent.objects.select_for_update(skip_locked=True)
                .filter(pk=event_id)
                .first()
            )
            if event is None:
                continue  # lo tiene otro worker
            if dispatch(event):
                ok += 1
            else:
                failed += 1
    return {"processed": ok, "failed": failed}
