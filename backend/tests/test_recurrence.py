"""Tests de tareas recurrentes: creacion, generacion de ocurrencias."""
import pytest
from django.utils import timezone
from datetime import timedelta

from apps.tasks.models import Task, RecurrenceRule


@pytest.mark.django_db
class TestRecurrenceRule:
    def test_crear_regla_diaria(self, authed_client):
        resp = authed_client.post("/api/tasks/", {
            "title": "Tarea recurrente",
            "recurrence_data": {
                "frequency": "daily",
                "interval": 1,
            },
        }, format="json")
        assert resp.status_code == 201
        assert resp.data["recurrence"] is not None
        assert resp.data["recurrence"]["frequency"] == "daily"

    def test_crear_regla_semanal(self, authed_client):
        resp = authed_client.post("/api/tasks/", {
            "title": "Reunion semanal",
            "recurrence_data": {
                "frequency": "weekly",
                "interval": 2,
            },
        }, format="json")
        assert resp.status_code == 201
        assert resp.data["recurrence"]["frequency"] == "weekly"
        assert resp.data["recurrence"]["interval"] == 2

    def test_tarea_sin_recurrencia(self, authed_client):
        resp = authed_client.post("/api/tasks/", {
            "title": "Tarea normal",
        }, format="json")
        assert resp.status_code == 201
        assert resp.data["recurrence"] is None


@pytest.mark.django_db
class TestRecurrenceGeneration:
    def test_completar_genera_siguiente(self, authed_client, user):
        rule = RecurrenceRule.objects.create(
            frequency="daily",
            interval=1,
        )
        now = timezone.now()
        task = Task.objects.create(
            owner=user,
            title="Tarea recurrente",
            state=Task.State.PENDING,
            due_date=now,
            recurrence=rule,
        )
        # Completar la tarea
        resp = authed_client.patch(f"/api/tasks/{task.id}/", {
            "state": "completed",
        }, format="json")
        assert resp.status_code == 200

        # Debe existir una nueva tarea pendiente
        new_tasks = Task.objects.filter(owner=user, state="pending", recurrence=rule)
        assert new_tasks.count() == 1
        new_task = new_tasks.first()
        assert new_task.title == "Tarea recurrente"
        # La nueva tarea tiene due_date posterior
        assert new_task.due_date > task.due_date

    def test_completar_tarea_no_recurrente_no_genera(self, authed_client, user):
        task = Task.objects.create(
            owner=user,
            title="Tarea normal",
            state=Task.State.PENDING,
        )
        authed_client.patch(f"/api/tasks/{task.id}/", {
            "state": "completed",
        }, format="json")
        assert Task.objects.filter(owner=user).count() == 1

    def test_recurrencia_con_count_limita_ocurrencias(self, authed_client, user):
        rule = RecurrenceRule.objects.create(
            frequency="daily",
            interval=1,
            count=2,
        )
        now = timezone.now()
        task = Task.objects.create(
            owner=user,
            title="Limitada",
            state=Task.State.PENDING,
            due_date=now,
            recurrence=rule,
        )
        # Completar tarea 1
        authed_client.patch(f"/api/tasks/{task.id}/", {
            "state": "completed",
        }, format="json")
        # Completar tarea 2 (generada)
        task2 = Task.objects.filter(owner=user, state="pending", recurrence=rule).first()
        authed_client.patch(f"/api/tasks/{task2.id}/", {
            "state": "completed",
        }, format="json")
        # No debe generar una tercera porque count=2
        assert Task.objects.filter(owner=user, state="pending", recurrence=rule).count() == 0

    def test_recurrencia_copia_etiquetas(self, authed_client, user, tag):
        rule = RecurrenceRule.objects.create(
            frequency="daily",
            interval=1,
        )
        now = timezone.now()
        task = Task.objects.create(
            owner=user,
            title="Con etiqueta",
            state=Task.State.PENDING,
            due_date=now,
            recurrence=rule,
        )
        task.tags.add(tag)
        authed_client.patch(f"/api/tasks/{task.id}/", {
            "state": "completed",
        }, format="json")
        new_task = Task.objects.filter(owner=user, state="pending", recurrence=rule).first()
        assert new_task is not None
        assert tag in new_task.tags.all()
