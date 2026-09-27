"""Round 3: out-of-office, intake público (schema), email opt-in y
nuevas acciones de automatización."""
from datetime import date, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.utils import timezone

from apps.automations.engine import execute_action
from apps.automations.models import AutomationRule
from apps.intake.models import IntakeForm
from apps.notifications.models import Notification, NotificationPreference
from apps.notifications.services import notify
from apps.projects.models import Project
from apps.tasks.models import Comment, Subtask

User = get_user_model()


@pytest.mark.django_db
class TestOutOfOffice:
    def test_patch_users_me_roundtrip(self, authed_client, user):
        resp = authed_client.patch(
            "/api/users/me/",
            {"out_of_office": True, "out_of_office_until": "2026-12-31"},
            format="json",
        )
        assert resp.status_code == 200
        user.refresh_from_db()
        assert user.out_of_office is True
        assert user.out_of_office_until == date(2026, 12, 31)
        # El serializer devuelve los campos
        assert resp.data["out_of_office"] is True
        assert resp.data["out_of_office_until"] == "2026-12-31"

    def test_get_users_me_exposes_fields(self, authed_client, user):
        user.out_of_office = True
        user.out_of_office_until = date(2026, 6, 15)
        user.save()
        resp = authed_client.get("/api/users/me/")
        assert resp.status_code == 200
        assert resp.data["out_of_office"] is True
        assert resp.data["out_of_office_until"] == "2026-06-15"

    def test_patch_auth_me(self, authed_client, user):
        resp = authed_client.patch(
            "/api/auth/me/", {"out_of_office": True}, format="json"
        )
        assert resp.status_code == 200
        user.refresh_from_db()
        assert user.out_of_office is True

    def test_clear_out_of_office(self, authed_client, user):
        user.out_of_office = True
        user.out_of_office_until = date(2026, 1, 1)
        user.save()
        resp = authed_client.patch(
            "/api/users/me/",
            {"out_of_office": False, "out_of_office_until": None},
            format="json",
        )
        assert resp.status_code == 200
        user.refresh_from_db()
        assert user.out_of_office is False
        assert user.out_of_office_until is None

    def test_defaults(self, user):
        assert user.out_of_office is False
        assert user.out_of_office_until is None


@pytest.mark.django_db
class TestPublicIntakeSchema:
    SCHEMA = [
        {"name": "title", "label": "Título", "type": "text", "required": True},
        {
            "name": "urgencia",
            "label": "Urgencia",
            "type": "select",
            "options": ["baja", "alta"],
        },
    ]

    def _form(self, user, project, enabled=True):
        return IntakeForm.objects.create(
            owner=user,
            project=project,
            name="Alta de bugs",
            description="Formulario público",
            schema=list(self.SCHEMA),
            enabled=enabled,
        )

    def test_get_schema(self, api_client, user, project):
        form = self._form(user, project)
        resp = api_client.get(f"/api/intake-forms/public/{form.public_token}/")
        assert resp.status_code == 200
        assert resp.data["id"] == form.id
        assert resp.data["name"] == "Alta de bugs"
        assert resp.data["description"] == "Formulario público"
        assert resp.data["schema"] == form.schema
        assert resp.data["enabled"] is True

    def test_404_disabled(self, api_client, user, project):
        form = self._form(user, project, enabled=False)
        resp = api_client.get(f"/api/intake-forms/public/{form.public_token}/")
        assert resp.status_code == 404

    def test_404_unknown_token(self, api_client):
        resp = api_client.get("/api/intake-forms/public/token-que-no-existe/")
        assert resp.status_code == 404

    def test_anonymous_allowed(self, api_client, user, project):
        # Sin credenciales: AllowAny
        form = self._form(user, project)
        resp = api_client.get(f"/api/intake-forms/public/{form.public_token}/")
        assert resp.status_code == 200


@pytest.mark.django_db
class TestEmailNotificationOptIn:
    def test_assignment_email_sent_when_opted_in(self, db, user, settings):
        settings.EMAIL_NOTIFICATIONS_ENABLED = True
        NotificationPreference.objects.create(
            user=user, notification_type="task_assigned", email_enabled=True
        )
        notify(user, "task_assigned", "Tarea asignada: X", body="Se te asignó")
        assert len(mail.outbox) == 1
        assert user.email in mail.outbox[0].to
        notif = Notification.objects.get(recipient=user)
        assert notif.sent_email is True

    def test_assignment_email_via_signal(self, db, user, other_user, task, settings):
        settings.EMAIL_NOTIFICATIONS_ENABLED = True
        NotificationPreference.objects.create(
            user=other_user,
            notification_type="task_assigned",
            email_enabled=True,
        )
        task.assignee = other_user
        task.save()
        assert len(mail.outbox) == 1
        assert other_user.email in mail.outbox[0].to

    def test_mention_and_reminder_types(self, db, user, settings):
        settings.EMAIL_NOTIFICATIONS_ENABLED = True
        for ntype in ("mention", "reminder"):
            NotificationPreference.objects.create(
                user=user, notification_type=ntype, email_enabled=True
            )
        notify(user, "mention", "Te mencionaron", body="@user")
        notify(user, "reminder", "Recordatorio", body="vence hoy")
        assert len(mail.outbox) == 2

    def test_no_email_when_pref_disabled(self, db, user, settings):
        settings.EMAIL_NOTIFICATIONS_ENABLED = True
        # preferencia por defecto: email_enabled=False
        notify(user, "task_assigned", "Tarea asignada: X", body="Se te asignó")
        assert len(mail.outbox) == 0
        # La notificación in-app sí se crea
        assert Notification.objects.filter(recipient=user).exists()

    def test_no_email_when_server_flag_off(self, db, user):
        # EMAIL_NOTIFICATIONS_ENABLED por defecto es False
        NotificationPreference.objects.create(
            user=user, notification_type="task_assigned", email_enabled=True
        )
        notify(user, "task_assigned", "Tarea asignada: X", body="Se te asignó")
        assert len(mail.outbox) == 0
        notif = Notification.objects.get(recipient=user)
        assert notif.sent_email is False

    def test_no_email_for_non_eligible_type(self, db, user, settings):
        settings.EMAIL_NOTIFICATIONS_ENABLED = True
        NotificationPreference.objects.create(
            user=user, notification_type="sprint_started", email_enabled=True
        )
        notify(user, "sprint_started", "Sprint iniciado", body="go")
        assert len(mail.outbox) == 0


@pytest.mark.django_db
class TestNewAutomationActions:
    @pytest.fixture(autouse=True)
    def setup_data(self, db, user, project):
        self.user = user
        self.project = project

    def _rule(self, action, params):
        return AutomationRule.objects.create(
            owner=self.user,
            name=f"rule-{action}",
            trigger=AutomationRule.Trigger.TASK_CREATED,
            action=action,
            action_params=params,
        )

    def test_create_subtask(self, task):
        rule = self._rule("create_subtask", {"title": "Revisar logs"})
        result = execute_action(rule, {"task": task})
        sub = Subtask.objects.get(task=task)
        assert sub.title == "Revisar logs"
        assert sub.is_done is False
        assert result["created_subtask_id"] == sub.id

    def test_create_subtask_no_title(self, task):
        rule = self._rule("create_subtask", {})
        result = execute_action(rule, {"task": task})
        assert "skipped" in result
        assert not Subtask.objects.filter(task=task).exists()

    def test_set_due_offset(self, task):
        assert task.due_date is None
        rule = self._rule("set_due_offset", {"days": 5})
        result = execute_action(rule, {"task": task})
        task.refresh_from_db()
        expected = timezone.now() + timedelta(days=5)
        assert abs((task.due_date - expected).total_seconds()) < 60
        assert "due_date" in result

    def test_set_due_offset_invalid(self, task):
        rule = self._rule("set_due_offset", {"days": "abc"})
        result = execute_action(rule, {"task": task})
        assert "error" in result
        task.refresh_from_db()
        assert task.due_date is None

    def test_post_comment(self, task):
        rule = self._rule("post_comment", {"text": "Auto-comentario"})
        result = execute_action(rule, {"task": task})
        comment = Comment.objects.get(task=task)
        assert comment.body == "Auto-comentario"
        assert comment.author == self.user  # owner de la regla
        assert result["comment_id"] == comment.id

    def test_post_comment_no_text(self, task):
        rule = self._rule("post_comment", {})
        result = execute_action(rule, {"task": task})
        assert "skipped" in result
        assert not Comment.objects.filter(task=task).exists()

    def test_move_to_project(self, task):
        target = Project.objects.create(owner=self.user, name="Destino")
        rule = self._rule("move_to_project", {"project_id": target.id})
        result = execute_action(rule, {"task": task})
        task.refresh_from_db()
        assert task.project_id == target.id
        assert result["new_project"] == "Destino"

    def test_move_to_project_not_accessible(self, db, task):
        other = User.objects.create_user(
            email="other2@test.com", username="other2", password="x"
        )
        foreign = Project.objects.create(owner=other, name="Ajeno")
        rule = self._rule("move_to_project", {"project_id": foreign.id})
        result = execute_action(rule, {"task": task})
        assert "error" in result
        task.refresh_from_db()
        assert task.project_id == self.project.id

    def test_move_to_project_requires_task(self):
        rule = self._rule("move_to_project", {"project_id": self.project.id})
        result = execute_action(rule, {})
        assert "error" in result
