"""Tests de Fase 8 (notificaciones) y Fase 9 (automatizaciones)."""
import pytest
from datetime import date, timedelta
from django.utils import timezone

from apps.tasks.models import Task, Comment, Sprint
from apps.notifications.models import Notification, NotificationPreference
from apps.notifications.services import notify, mark_as_read, mark_all_as_read, get_unread_count
from apps.automations.models import AutomationRule, AutomationLog
from apps.automations.engine import (
    evaluate_conditions, execute_action, trigger_automation, run_daily_checks,
)


# --- Fase 8: Notificaciones ---

@pytest.mark.django_db
class TestNotifications:
    def test_crear_notificacion_in_app(self, user):
        notif = notify(
            recipient=user,
            notification_type="task_assigned",
            title="Tarea asignada",
            body="Se te asignó una tarea",
        )
        assert notif is not None
        assert notif.read is False
        assert notif.sent_in_app is True

    def test_marcar_como_leida(self, user):
        notif = notify(user, "custom", "Test")
        result = mark_as_read(notif.id, user)
        assert result.read is True
        assert result.read_at is not None

    def test_marcar_todas_como_leidas(self, user):
        notify(user, "custom", "Test 1")
        notify(user, "custom", "Test 2")
        notify(user, "custom", "Test 3")
        count = mark_all_as_read(user)
        assert count == 3
        assert get_unread_count(user) == 0

    def test_contar_no_leidas(self, user):
        notify(user, "custom", "Test 1")
        notify(user, "custom", "Test 2")
        assert get_unread_count(user) == 2

    def test_preferencias_desactivadas(self, user):
        """Si in_app está desactivado, no se crea la notificación."""
        NotificationPreference.objects.create(
            user=user, notification_type="custom",
            in_app_enabled=False, email_enabled=False,
        )
        notif = notify(user, "custom", "No debe crearse")
        assert notif is None
        assert Notification.objects.filter(recipient=user).count() == 0

    def test_notificacion_por_comentario(self, user, other_user, task):
        """Al añadir un comentario, el owner de la tarea recibe notificación."""
        # task es del user, other_user comenta
        Comment.objects.create(task=task, author=other_user, body="Hola")
        notifs = Notification.objects.filter(recipient=user, type="task_commented")
        assert notifs.count() == 1
        assert "Hola" in notifs.first().body

    def test_no_notificar_al_autor(self, user, task):
        """El autor del comentario no recibe notificación de su propio comentario."""
        Comment.objects.create(task=task, author=user, body="Mi comentario")
        notifs = Notification.objects.filter(recipient=user, type="task_commented")
        assert notifs.count() == 0

    def test_notificacion_sprint_iniciado(self, user):
        sprint = Sprint.objects.create(
            owner=user, name="S1", state="planned",
            start_date=date.today(), end_date=date.today() + timedelta(days=14),
        )
        sprint.state = "active"
        sprint.save()
        notifs = Notification.objects.filter(recipient=user, type="sprint_started")
        assert notifs.count() == 1


@pytest.mark.django_db
class TestNotificationAPI:
    def test_listar_notificaciones(self, authed_client, user):
        notify(user, "custom", "Test API")
        resp = authed_client.get("/api/notifications/")
        assert resp.status_code == 200
        data = resp.data["results"] if "results" in resp.data else resp.data
        assert len(data) == 1

    def test_contar_no_leidas_api(self, authed_client, user):
        notify(user, "custom", "Test")
        resp = authed_client.get("/api/notifications/unread_count/")
        assert resp.status_code == 200
        assert resp.data["count"] == 1

    def test_marcar_todas_leidas_api(self, authed_client, user):
        notify(user, "custom", "Test 1")
        notify(user, "custom", "Test 2")
        resp = authed_client.post("/api/notifications/mark_all_read/")
        assert resp.status_code == 200
        assert resp.data["marked"] == 2

    def test_marcar_una_leida_api(self, authed_client, user):
        notif = notify(user, "custom", "Test")
        resp = authed_client.post(f"/api/notifications/{notif.id}/mark_read/")
        assert resp.status_code == 200
        assert resp.data["read"] is True

    def test_preferencias_api(self, authed_client, user):
        resp = authed_client.get("/api/notification-preferences/")
        assert resp.status_code == 200
        data = resp.data["results"] if "results" in resp.data else resp.data
        # Debe crear preferencias para todos los tipos
        assert len(data) > 0


# --- Fase 9: Automatizaciones ---

@pytest.mark.django_db
class TestAutomationConditions:
    def test_condicion_equals(self):
        conditions = [{"field": "state", "operator": "equals", "value": "blocked"}]
        assert evaluate_conditions(conditions, {"state": "blocked"}) is True
        assert evaluate_conditions(conditions, {"state": "pending"}) is False

    def test_condicion_contains(self):
        conditions = [{"field": "title", "operator": "contains", "value": "bug"}]
        assert evaluate_conditions(conditions, {"title": "Fix bug now"}) is True
        assert evaluate_conditions(conditions, {"title": "Feature"}) is False

    def test_condicion_gt(self):
        conditions = [{"field": "priority", "operator": "gt", "value": "3"}]
        assert evaluate_conditions(conditions, {"priority": 4}) is True
        assert evaluate_conditions(conditions, {"priority": 2}) is False

    def test_multiples_condiciones_and(self):
        conditions = [
            {"field": "state", "operator": "equals", "value": "blocked"},
            {"field": "priority", "operator": "gt", "value": "2"},
        ]
        assert evaluate_conditions(conditions, {"state": "blocked", "priority": 3}) is True
        assert evaluate_conditions(conditions, {"state": "blocked", "priority": 1}) is False


@pytest.mark.django_db
class TestAutomationActions:
    def test_action_set_priority(self, user, task):
        rule = AutomationRule.objects.create(
            owner=user, name="Test",
            trigger="task_blocked",
            action="set_priority",
            action_params={"priority": 0},
        )
        result = execute_action(rule, {"task": task})
        task.refresh_from_db()
        assert task.priority == 0
        assert result["new_priority"] == 0

    def test_action_set_state(self, user, task):
        rule = AutomationRule.objects.create(
            owner=user, name="Test",
            trigger="task_overdue",
            action="set_state",
            action_params={"state": "blocked"},
        )
        execute_action(rule, {"task": task})
        task.refresh_from_db()
        assert task.state == "blocked"

    def test_action_create_notification(self, user, task):
        rule = AutomationRule.objects.create(
            owner=user, name="Test",
            trigger="task_completed",
            action="create_notification",
            action_params={"title": "Completada!", "body": "Bien hecho"},
        )
        execute_action(rule, {"task": task, "user": user})
        notif = Notification.objects.filter(recipient=user, title="Completada!")
        assert notif.count() == 1

    def test_action_create_task(self, user):
        rule = AutomationRule.objects.create(
            owner=user, name="Test",
            trigger="sprint_closed",
            action="create_task",
            action_params={"title": "Tarea de seguimiento", "priority": 2},
        )
        result = execute_action(rule, {"user": user})
        assert "created_task_id" in result
        new_task = Task.objects.get(id=result["created_task_id"])
        assert new_task.title == "Tarea de seguimiento"


@pytest.mark.django_db
class TestAutomationEngine:
    def test_trigger_ejecuta_regla(self, user, task):
        AutomationRule.objects.create(
            owner=user, name="Auto-block",
            trigger="task_blocked",
            action="set_priority",
            action_params={"priority": 0},
            conditions=[{"field": "state", "operator": "equals", "value": "blocked"}],
        )
        task.state = "blocked"
        task.save()

        results = trigger_automation("task_blocked", {"task": task, "state": "blocked"})
        assert len(results) == 1
        task.refresh_from_db()
        assert task.priority == 0

    def test_trigger_sin_reglas(self, user):
        results = trigger_automation("task_created", {"user": user})
        assert results == []

    def test_trigger_condicion_no_cumple(self, user, task):
        AutomationRule.objects.create(
            owner=user, name="Auto-block",
            trigger="task_blocked",
            action="set_priority",
            action_params={"priority": 0},
            conditions=[{"field": "state", "operator": "equals", "value": "blocked"}],
            enabled=True,
        )
        # El contexto no cumple la condición (state=pending)
        results = trigger_automation("task_blocked", {"task": task, "state": "pending"})
        assert len(results) == 0
        # Debe haber un log de skipped
        assert AutomationLog.objects.filter(status="skipped").count() == 1

    def test_regla_deshabilitada_no_ejecuta(self, user, task):
        AutomationRule.objects.create(
            owner=user, name="Disabled",
            trigger="task_blocked",
            action="set_priority",
            action_params={"priority": 0},
            enabled=False,
        )
        results = trigger_automation("task_blocked", {"task": task, "user": user})
        assert results == []

    def test_log_de_ejecucion(self, user, task):
        rule = AutomationRule.objects.create(
            owner=user, name="Logged",
            trigger="task_completed",
            action="create_notification",
            action_params={"title": "Done"},
        )
        trigger_automation("task_completed", {"task": task, "user": user})
        log = AutomationLog.objects.filter(rule=rule, status="success")
        assert log.count() == 1
        rule.refresh_from_db()
        assert rule.trigger_count == 1
        assert rule.last_triggered_at is not None


@pytest.mark.django_db
class TestDailyChecks:
    def test_tarea_vencida_dispara_automatizacion(self, user):
        AutomationRule.objects.create(
            owner=user, name="Overdue alert",
            trigger="task_overdue",
            action="create_notification",
            action_params={"title": "Tarea vencida"},
        )
        Task.objects.create(
            owner=user, title="Vencida",
            state="pending",
            due_date=date.today() - timedelta(days=1),
        )
        results = run_daily_checks()
        assert len(results) > 0
        assert Notification.objects.filter(title="Tarea vencida").count() == 1


@pytest.mark.django_db
class TestAutomationAPI:
    def test_crear_regla(self, authed_client):
        resp = authed_client.post("/api/automation-rules/", {
            "name": "Mi regla",
            "trigger": "task_blocked",
            "action": "set_priority",
            "action_params": {"priority": 0},
            "conditions": [],
            "enabled": True,
        }, format="json")
        assert resp.status_code == 201
        assert resp.data["name"] == "Mi regla"

    def test_listar_reglas(self, authed_client, user):
        AutomationRule.objects.create(
            owner=user, name="R1",
            trigger="task_blocked", action="set_priority",
            action_params={"priority": 0},
        )
        resp = authed_client.get("/api/automation-rules/")
        assert resp.status_code == 200
        data = resp.data["results"] if "results" in resp.data else resp.data
        assert len(data) == 1

    def test_logs_de_regla(self, authed_client, user):
        rule = AutomationRule.objects.create(
            owner=user, name="R1",
            trigger="task_blocked", action="set_priority",
            action_params={"priority": 0},
        )
        AutomationLog.objects.create(
            rule=rule, status="success",
            trigger_data={}, action_result={"ok": True},
        )
        resp = authed_client.get(f"/api/automation-rules/{rule.id}/logs/")
        assert resp.status_code == 200
        data = resp.data if isinstance(resp.data, list) else resp.data["results"]
        assert len(data) == 1

    def test_probar_regla(self, authed_client, user, task):
        rule = AutomationRule.objects.create(
            owner=user, name="Test rule",
            trigger="task_blocked",
            action="set_priority",
            action_params={"priority": 1},
        )
        resp = authed_client.post(f"/api/automation-rules/{rule.id}/test/")
        assert resp.status_code == 200
        assert "results" in resp.data
