"""Signals para sincronizar tareas con GitHub automáticamente."""
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.tasks.models import Task


@receiver(post_save, sender=Task)
def sync_task_to_github(sender, instance, created, **kwargs):
    """Cuando una tarea con link de GitHub se guarda, sincroniza el issue."""
    # Solo si la tarea tiene un link de GitHub y no estamos en medio de un sync
    link = getattr(instance, "github_link", None)
    if not link:
        return
    # Evitar recursión: si el sync está actualizando la tarea, no re-sync
    if getattr(instance, "_syncing_from_github", False):
        return
    try:
        from .sync_service import sync_task_to_issue
        sync_task_to_issue(instance)
    except Exception:
        # Log pero no romper el save de la tarea
        import logging
        logger = logging.getLogger(__name__)
        logger.exception(f"Error sincronizando tarea {instance.id} a GitHub")
