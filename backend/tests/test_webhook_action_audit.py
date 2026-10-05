"""Acción call_webhook de automatizaciones + export del audit log."""
from unittest.mock import patch

import pytest
import requests as _requests  # noqa: F401  (parchear el módulo real)
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.automations.engine import execute_action
from apps.automations.models import AutomationRule
from apps.collaboration.models import AuditLog
from apps.tasks.models import Task

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(email="u@t.dev", username="u", password="x" * 20)


def _rule(owner, **kw):
    kw.setdefault("trigger", "task_created")
    kw.setdefault("action", "call_webhook")
    return AutomationRule.objects.create(owner=owner, name="R", **kw)


class TestCallWebhookAction:
    def test_no_url_skips(self, user):
        rule = _rule(user, action_params={})
        assert "skipped" in execute_action(rule, {})

    def test_internal_url_rejected(self, user):
        rule = _rule(
            user, action_params={"url": "http://169.254.169.254/meta"}
        )
        result = execute_action(rule, {})
        assert "error" in result

    def test_success_posts_payload(self, user):
        task = Task.objects.create(owner=user, title="T")
        rule = _rule(
            user, action_params={"url": "https://hooks.example.com/x"}
        )
        with patch("apps.integrations_chat.services._is_safe_url", return_value=True), patch("requests.post") as post:
            post.return_value.status_code = 200
            result = execute_action(rule, {"task": task})
        assert result["webhook_status"] == 200
        import json
        body = json.loads(post.call_args.kwargs["data"])
        assert body["task"]["id"] == task.id
        assert body["trigger"] == "task_created"
        assert post.call_args.kwargs["allow_redirects"] is False

    def test_hmac_signature(self, user):
        rule = _rule(
            user,
            action_params={
                "url": "https://hooks.example.com/x", "secret": "s3cr3t"
            },
        )
        with patch("apps.integrations_chat.services._is_safe_url", return_value=True), patch("requests.post") as post:
            post.return_value.status_code = 200
            execute_action(rule, {})
        sig = post.call_args.kwargs["headers"]["X-Hub-Signature-256"]
        assert sig.startswith("sha256=")

    def test_http_error_is_failed(self, user):
        rule = _rule(
            user, action_params={"url": "https://hooks.example.com/x"}
        )
        with patch("apps.integrations_chat.services._is_safe_url", return_value=True), patch("requests.post") as post:
            post.return_value.status_code = 500
            result = execute_action(rule, {})
        assert "error" in result

    def test_works_without_task(self, user):
        """La acción también vale para triggers sin tarea (sprint, daily)."""
        rule = _rule(
            user, action_params={"url": "https://hooks.example.com/x"}
        )
        with patch("apps.integrations_chat.services._is_safe_url", return_value=True), patch("requests.post") as post:
            post.return_value.status_code = 200
            result = execute_action(rule, {"sprint": None})
        assert result["webhook_status"] == 200
        body = __import__("json").loads(post.call_args.kwargs["data"])
        assert body["task"] is None

    def test_serializer_rejects_internal_url(self, user):
        r = APIClient()
        r.force_authenticate(user=user)
        resp = r.post(
            "/api/automation-rules/",
            {
                "name": "W", "trigger": "task_created",
                "action": "call_webhook",
                "action_params": {"url": "http://localhost:6379/"},
            },
            format="json",
        )
        assert resp.status_code == 400


class TestAuditExport:
    def test_csv_export(self, user):
        AuditLog.objects.create(
            actor=user, action="create", resource_type="project",
            resource_id=1, resource_name="P",
        )
        c = APIClient()
        c.force_authenticate(user=user)
        resp = c.get("/api/audit-logs/export/")
        assert resp.status_code == 200
        assert resp["Content-Type"] == "text/csv"
        assert "create,project" in resp.content.decode()
        # la exportación queda auditada
        assert AuditLog.objects.filter(
            actor=user, action="export"
        ).exists()

    def test_jsonl_export_scoped_to_self(self, user):
        other = User.objects.create_user(
            email="o@t.dev", username="o", password="x" * 20
        )
        AuditLog.objects.create(
            actor=user, action="login", resource_type="user"
        )
        AuditLog.objects.create(
            actor=other, action="delete", resource_type="project"
        )
        c = APIClient()
        c.force_authenticate(user=user)
        resp = c.get("/api/audit-logs/export/?fmt=jsonl")
        body = resp.content.decode()
        assert '"login"' in body
        assert '"delete"' not in body


