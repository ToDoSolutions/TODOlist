"""Beat task: reintenta eventos del outbox fallidos/pendientes."""
import logging

from celery import shared_task

from .bus import process_pending_events

logger = logging.getLogger(__name__)


@shared_task
def process_outbox_events():
    return process_pending_events()
