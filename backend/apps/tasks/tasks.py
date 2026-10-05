"""Tareas de Celery para generación de tareas recurrentes."""
import logging

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from apps.tasks.models import RecurrenceRule, Task

logger = logging.getLogger(__name__)


def _generate_recurring_tasks():
    """Genera las ocurrencias pendientes de todas las reglas activas.

    Recorre cada RecurrenceRule activa (que no haya superado ``until`` ni
    ``count``), localiza la última tarea generada con esa regla y, si la
    próxima fecha de recurrencia ya pasó, crea una nueva tarea heredando
    título, descripción, proyecto, etiquetas y prioridad.

    Returns:
        dict: Resumen con ``rules_processed``, ``tasks_created`` y ``errors``.
    """
    now = timezone.now()
    rules_processed = 0
    tasks_created = 0
    errors = []

    # Reglas activas: con owner, sin until vencido y sin count alcanzado.
    # until y count son opcionales (null = sin límite), por eso se filtra
    # en Python para combinar correctamente ambas condiciones.
    active_rules = []
    for rule in RecurrenceRule.objects.filter(owner__isnull=False):
        if rule.until and now > rule.until:
            continue
        if rule.count and rule.occurrences_generated >= rule.count:
            continue
        active_rules.append(rule)

    for rule in active_rules:
        rules_processed += 1
        try:
            with transaction.atomic():
                # Última tarea generada con esta regla
                last_task = (
                    Task.objects.filter(recurrence=rule)
                    .order_by("-created_at", "-id")
                    .first()
                )
                if last_task is None:
                    logger.debug(
                        "Regla %s sin tareas previas, se omite.", rule.id
                    )
                    continue

                # Calcular próxima fecha desde la última tarea
                base_date = last_task.due_date or last_task.created_at
                next_due = rule.next_due_date(base_date)
                if next_due is None:
                    logger.warning(
                        "Regla %s: frequency no soportada (%s).",
                        rule.id,
                        rule.frequency,
                    )
                    continue

                # Solo generar si la próxima fecha ya pasó
                if next_due > now:
                    logger.debug(
                        "Regla %s: próxima ocurrencia %s aún no vence.",
                        rule.id,
                        next_due,
                    )
                    continue

                # Verificar límites antes de incrementar
                if rule.count and rule.occurrences_generated >= rule.count:
                    logger.info(
                        "Regla %s alcanzó count (%s), se detiene.",
                        rule.id,
                        rule.count,
                    )
                    continue
                if rule.until and next_due > rule.until:
                    logger.info(
                        "Regla %s: próxima ocurrencia %s supera until %s.",
                        rule.id,
                        next_due,
                        rule.until,
                    )
                    continue

                from .services import next_position_seq
                pos, seq = next_position_seq(last_task.owner, last_task.project)
                new_task = Task.objects.create(
                    owner=last_task.owner,
                    project=last_task.project,
                    title=last_task.title,
                    description=last_task.description,
                    state=Task.State.PENDING,
                    priority=last_task.priority,
                    due_date=next_due,
                    recurrence=rule,
                    position=pos,
                    seq=seq,
                )
                if last_task.tags.exists():
                    new_task.tags.set(last_task.tags.all())
                # Multi-homing: la ocurrencia hereda los hogares extra
                # (misma regla que Task.generate_next_occurrence)
                new_task.extra_projects.set(last_task.extra_projects.all())

                rule.occurrences_generated += 1
                rule.save(update_fields=["occurrences_generated"])

                tasks_created += 1
                logger.info(
                    "Tarea recurrente creada: id=%s, título=%r, due=%s (regla %s)",
                    new_task.id,
                    new_task.title,
                    new_task.due_date,
                    rule.id,
                )
        except Exception as exc:
            errors.append({"rule_id": rule.id, "error": str(exc)})
            logger.exception(
                "Error generando ocurrencias para la regla %s",
                rule.id,
            )

    summary = {
        "rules_processed": rules_processed,
        "tasks_created": tasks_created,
        "errors": errors,
    }
    logger.info(
        "Generación de tareas recurrentes completada: %s reglas procesadas, "
        "%s tareas creadas, %s errores.",
        rules_processed,
        tasks_created,
        len(errors),
    )
    return summary


@shared_task
def generate_recurring_tasks():
    """Tarea de Celery que genera tareas recurrentes pendientes.

    Se ejecuta diariamente (configurada en ``CELERY_BEAT_SCHEDULE``) y
    también puede invocarse manualmente.
    """
    return _generate_recurring_tasks()


@shared_task
def send_due_reminders():
    """Envía notificaciones de recordatorio para tareas con reminder_at vencido.

    Recorre las tareas con ``reminder_at <= now``, ``reminder_sent=False``
    y estado no terminal (no completed/cancelled/archived), crea una
    Notification de tipo ``reminder`` al owner y marca el recordatorio
    como enviado. Se ejecuta cada minuto vía beat (``send-due-reminders``).

    Returns:
        dict: Resumen con ``reminders_sent``.
    """
    from apps.notifications.services import notify

    now = timezone.now()
    due = Task.objects.filter(
        reminder_at__isnull=False,
        reminder_at__lte=now,
        reminder_sent=False,
    ).exclude(
        state__in=[
            Task.State.COMPLETED,
            Task.State.CANCELLED,
            Task.State.ARCHIVED,
        ]
    ).select_related("owner")

    sent = 0
    for task in due:
        # Claim atómico ANTES de notificar: dos ejecuciones solapadas
        # (worker duplicado, beat tras deploy) no pueden enviar el
        # mismo recordatorio. update() evita bump de version y signals.
        claimed = Task.objects.filter(
            pk=task.pk, reminder_sent=False
        ).update(reminder_sent=True)
        if not claimed:
            continue
        try:
            notify(
                recipient=task.owner,
                notification_type="reminder",
                title=f"Recordatorio: {task.title}",
                body=f"La tarea '{task.title}' tiene un recordatorio programado",
                task=task,
                action_url=f"/app/tasks/{task.id}",
            )
            sent += 1
        except Exception:
            logger.exception(
                "Error enviando recordatorio de la tarea %s", task.id
            )
            # Deshacer el claim para que el siguiente ciclo reintente —
            # mejor un posible duplicado que un recordatorio perdido.
            try:
                Task.objects.filter(pk=task.pk).update(reminder_sent=False)
            except Exception:
                logger.exception(
                    "No se pudo deshacer el claim de reminder %s", task.id
                )
    logger.info("send_due_reminders: %s recordatorios enviados", sent)
    return {"reminders_sent": sent}
