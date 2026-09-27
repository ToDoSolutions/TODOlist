"""Policies: decisiones de autorización del dominio tasks.

Centraliza la lógica "¿puede este usuario hacer X sobre esta tarea?" que
antes estaba inline en los ViewSets. Misma fuente de verdad
(``Task.objects.for_user``) — solo se extrae la decisión.
"""
from .models import Task


def can_write_task(user, task) -> bool:
    """Escritura sobre una tarea: owner o rol editor/owner en su proyecto."""
    return Task.objects.for_user(user, write=True).filter(pk=task.pk).exists()


def assert_can_write_task(user, task):
    """Igual que can_write_task pero lanza PermissionDenied (uso en views)."""
    from rest_framework.exceptions import PermissionDenied

    if not can_write_task(user, task):
        raise PermissionDenied("Tienes acceso de solo lectura a esta tarea")
