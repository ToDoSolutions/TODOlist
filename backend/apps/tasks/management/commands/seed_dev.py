"""Seed de desarrollo: crea un usuario demo, un proyecto, etiquetas y tareas."""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from apps.projects.models import Project
from apps.tags.models import Tag
from apps.tasks.models import Task, Subtask

User = get_user_model()

DEMO_EMAIL = "demo@todolist.local"
DEMO_PASSWORD = "demo12345"


class Command(BaseCommand):
    help = "Crea datos de demo para desarrollo (idempotente)."

    def handle(self, *args, **options):
        user, created = User.objects.get_or_create(
            email=DEMO_EMAIL,
            defaults={"username": "demo"},
        )
        if created:
            user.set_password(DEMO_PASSWORD)
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Usuario demo creado: {DEMO_EMAIL}"))
        else:
            self.stdout.write(f"Usuario demo ya existe: {DEMO_EMAIL}")

        project, _ = Project.objects.get_or_create(
            owner=user, name="Lanzamiento MVP",
            defaults={"description": "Proyecto de ejemplo para el MVP."},
        )

        tags = {}
        for name, color in [
            ("Trabajo", "#1976d2"),
            ("Personal", "#43a047"),
            ("Urgente", "#e53935"),
        ]:
            tags[name], _ = Tag.objects.get_or_create(
                owner=user, name=name, defaults={"color": color}
            )

        now = timezone.now()

        Task.objects.get_or_create(
            owner=user, project=project, title="Definir esquema de base de datos",
            defaults={
                "state": Task.State.COMPLETED,
                "priority": Task.Priority.P1_VERY_HIGH,
                "completed_at": now - timedelta(days=2),
            },
        )

        Task.objects.get_or_create(
            owner=user, project=project, title="Implementar API de tareas",
            defaults={
                "state": Task.State.IN_PROGRESS,
                "priority": Task.Priority.P0_CRITICAL,
                "due_date": now + timedelta(days=1),
            },
        )

        task, _ = Task.objects.get_or_create(
            owner=user, project=project, title="Diseñar vistas Kanban y Lista",
            defaults={
                "state": Task.State.PENDING,
                "priority": Task.Priority.P2_HIGH,
                "due_date": now + timedelta(days=3),
            },
        )
        task.tags.set([tags["Trabajo"], tags["Urgente"]])
        Subtask.objects.get_or_create(
            task=task, title="Columnas por estado", defaults={"order": 0}
        )
        Subtask.objects.get_or_create(
            task=task, title="Drag & drop básico", defaults={"order": 1}
        )

        Task.objects.get_or_create(
            owner=user, project=None, title="Comprar pan",
            defaults={
                "state": Task.State.PENDING,
                "priority": Task.Priority.P4_LOW,
                "due_date": now + timedelta(hours=6),
            },
        )

        self.stdout.write(self.style.SUCCESS("Seed completado."))
