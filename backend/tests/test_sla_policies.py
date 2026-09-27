"""Tests de SlaPolicy y escalado SLA en run_daily_checks."""
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.automations.engine import _run_sla_escalations
from apps.automations.models import SlaPolicy
from apps.notifications.models import Notification
from apps.tasks.models import Task

User = get_user_model()


@pytest.fixture
def user(db):
    u, _ = User.objects.get_or_create(
        username="sla_user", defaults={"email": "sla@x.com"}
    )
    return u


def _old_task(user, priority=3, hours=100, state="pending"):
    """Tarea creada hace `hours` horas (bypasea auto_now_add)."""
    task = Task.objects.create(owner=user, title="SLA task", priority=priority, state=state)
    Task.objects.filter(pk=task.pk).update(
        created_at=timezone.now() - timedelta(hours=hours)
    )
    task.refresh_from_db()
    return task


@pytest.mark.django_db
class TestSlaEscalation:
    def test_escala_prioridad_al_incumplir(self, user):
        SlaPolicy.objects.create(
            owner=user, name="P3", priority=3, resolution_hours=48,
        )
        task = _old_task(user, priority=3, hours=100)
        _run_sla_escalations(timezone.now())
        task.refresh_from_db()
        assert task.priority == 2  # escalado un nivel
        assert task.tags.filter(name="sla-breached").exists()

    def test_no_escala_si_dentro_del_sla(self, user):
        SlaPolicy.objects.create(
            owner=user, name="P3", priority=3, resolution_hours=48,
        )
        task = _old_task(user, priority=3, hours=10)
        _run_sla_escalations(timezone.now())
        task.refresh_from_db()
        assert task.priority == 3
        assert not task.tags.filter(name="sla-breached").exists()

    def test_no_escala_tareas_completadas(self, user):
        SlaPolicy.objects.create(
            owner=user, name="P3", priority=3, resolution_hours=48,
        )
        task = _old_task(user, priority=3, hours=100, state="completed")
        _run_sla_escalations(timezone.now())
        task.refresh_from_db()
        assert task.priority == 3
        assert not task.tags.filter(name="sla-breached").exists()

    def test_no_baja_de_p1(self, user):
        """P1 es el tope: no se escala a P0 inexistente."""
        SlaPolicy.objects.create(
            owner=user, name="P1", priority=1, resolution_hours=4,
        )
        task = _old_task(user, priority=1, hours=100)
        _run_sla_escalations(timezone.now())
        task.refresh_from_db()
        assert task.priority == 1

    def test_no_reescala_marcada(self, user):
        """Una tarea ya marcada sla-breached no se vuelve a escalar."""
        from apps.tags.models import Tag
        SlaPolicy.objects.create(
            owner=user, name="P3", priority=3, resolution_hours=48,
        )
        task = _old_task(user, priority=3, hours=100)
        tag = Tag.objects.create(owner=user, name="sla-breached")
        task.tags.add(tag)
        _run_sla_escalations(timezone.now())
        task.refresh_from_db()
        assert task.priority == 3  # ya marcada → no tocar

    def test_notifica_owner_y_assignee(self, user):
        assignee, _ = User.objects.get_or_create(
            username="sla_asg", defaults={"email": "sla_asg@x.com"}
        )
        SlaPolicy.objects.create(
            owner=user, name="P3", priority=3, resolution_hours=48,
        )
        task = _old_task(user, priority=3, hours=100)
        task.assignee = assignee
        task.save()
        _run_sla_escalations(timezone.now())
        assert Notification.objects.filter(
            recipient=user, type="sla_breach"
        ).exists()
        assert Notification.objects.filter(
            recipient=assignee, type="sla_breach"
        ).exists()

    def test_policy_deshabilitada_no_escala(self, user):
        SlaPolicy.objects.create(
            owner=user, name="P3", priority=3, resolution_hours=48, enabled=False,
        )
        task = _old_task(user, priority=3, hours=100)
        _run_sla_escalations(timezone.now())
        task.refresh_from_db()
        assert task.priority == 3

    def test_no_afecta_otros_usuarios(self, user):
        other, _ = User.objects.get_or_create(
            username="sla_other", defaults={"email": "sla_o@x.com"}
        )
        SlaPolicy.objects.create(
            owner=user, name="P3", priority=3, resolution_hours=48,
        )
        task = _old_task(other, priority=3, hours=100)
        _run_sla_escalations(timezone.now())
        task.refresh_from_db()
        assert task.priority == 3


@pytest.mark.django_db
class TestSlaPolicyApi:
    def test_crud(self, authed_client, user):
        resp = authed_client.post("/api/sla-policies/", {
            "name": "SLA críticas",
            "priority": 1,
            "response_hours": 4,
            "resolution_hours": 24,
        })
        assert resp.status_code == 201
        assert SlaPolicy.objects.filter(owner=user, name="SLA críticas").exists()

    def test_response_no_puede_superar_resolution(self, authed_client):
        resp = authed_client.post("/api/sla-policies/", {
            "name": "Inválida",
            "priority": 2,
            "response_hours": 100,
            "resolution_hours": 24,
        })
        assert resp.status_code == 400

    def test_lista_solo_propias(self, authed_client, user):
        other, _ = User.objects.get_or_create(
            username="sla_o2", defaults={"email": "sla_o2@x.com"}
        )
        SlaPolicy.objects.create(owner=other, name="Ajena", priority=1)
        resp = authed_client.get("/api/sla-policies/")
        assert resp.status_code == 200
        names = [p["name"] for p in resp.json()]
        assert "Ajena" not in names

    def test_unique_owner_priority(self, authed_client, user):
        SlaPolicy.objects.create(owner=user, name="A", priority=1)
        resp = authed_client.post("/api/sla-policies/", {
            "name": "B", "priority": 1,
        })
        assert resp.status_code == 400
