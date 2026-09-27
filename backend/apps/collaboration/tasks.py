"""Tareas de Celery para colaboración: sync de calendarios externos."""
import datetime as dt
import logging

import requests
from celery import shared_task
from django.utils import timezone

from apps.integrations_chat.services import _is_safe_url

from .models import ExternalCalendar, ExternalEvent

logger = logging.getLogger(__name__)

MAX_FEED_BYTES = 5 * 1024 * 1024  # 5 MB


def _to_aware_dt(value):
    """Convierte un valor DTSTART/DTEND de icalendar a datetime aware UTC.

    Devuelve (datetime, all_day): ``all_day=True`` cuando el feed usa
    ``VALUE=DATE`` (date sin hora).
    """
    if isinstance(value, dt.datetime):
        if timezone.is_naive(value):
            value = timezone.make_aware(value, dt.UTC)
        return value, False
    if isinstance(value, dt.date):
        return dt.datetime.combine(
            value, dt.time.min, tzinfo=dt.UTC
        ), True
    return None, False


def sync_external_calendar(calendar):
    """Descarga y parsea el feed iCal de un ``ExternalCalendar``.

    Sustituye los ``ExternalEvent`` previos por los del feed (el feed es la
    fuente de verdad) y actualiza ``last_synced_at``/``last_error``.
    Devuelve el número de eventos importados, o ``None`` si falló.
    """
    from icalendar import Calendar as ICalCalendar

    def _fail(msg):
        calendar.last_error = msg[:500]
        calendar.save(update_fields=["last_error"])
        logger.warning("ExternalCalendar %s sync failed: %s", calendar.pk, msg)

    if not _is_safe_url(calendar.url):
        return _fail("URL no permitida (destino interno o no resoluble)")

    try:
        resp = requests.get(calendar.url, timeout=15)
        resp.raise_for_status()
        content = resp.content[:MAX_FEED_BYTES]
    except requests.RequestException as e:
        return _fail(f"Error de red: {type(e).__name__}: {e}")

    try:
        ical = ICalCalendar.from_ical(content)
    except Exception as e:  # noqa: BLE001  # boundary intencional: feed externo inválido
        return _fail(f"Error parseando iCal: {type(e).__name__}")

    events = []
    for component in ical.walk("VEVENT"):
        dtstart_prop = component.get("DTSTART")
        if dtstart_prop is None:
            continue
        dtstart, all_day = _to_aware_dt(dtstart_prop.dt)
        if dtstart is None:
            continue
        dtend = None
        dtend_prop = component.get("DTEND")
        if dtend_prop is not None:
            dtend, _ = _to_aware_dt(dtend_prop.dt)
        summary = component.get("SUMMARY")
        events.append(ExternalEvent(
            calendar=calendar,
            uid=str(component.get("UID", ""))[:255],
            summary=str(summary)[:500] if summary else "",
            dtstart=dtstart,
            dtend=dtend,
            all_day=all_day,
        ))

    calendar.events.all().delete()
    ExternalEvent.objects.bulk_create(events)
    calendar.last_synced_at = timezone.now()
    calendar.last_error = ""
    calendar.save(update_fields=["last_synced_at", "last_error"])
    return len(events)


@shared_task
def sync_external_calendars():
    """Sincroniza todos los calendarios externos activos.

    Ejecutada por Celery beat cada 15 minutos. Los errores de cada
    calendario se registran en ``last_error`` sin abortar el resto.
    """
    synced = 0
    for cal in ExternalCalendar.objects.filter(is_active=True).iterator():
        try:
            if sync_external_calendar(cal) is not None:
                synced += 1
        except Exception:  # un feed roto no debe tumbar el batch
            logger.exception(
                "Error sincronizando ExternalCalendar %s", cal.pk
            )
    return f"Synced {synced} external calendars"
