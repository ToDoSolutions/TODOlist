"""Tareas de Celery para automatizaciones."""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def run_daily_checks_task():
    """Ejecuta chequeos diarios de automatizaciones."""
    from .engine import run_daily_checks
    results = run_daily_checks()
    return f"Daily checks: {len(results)} actions triggered"
