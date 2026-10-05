"""Tests del endpoint POST /api/tasks/plan-day/ (time-blocking)."""
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.tasks.models import Task

pytestmark = pytest.mark.django_db
User = get_user_model()
URL = "/api/tasks/plan-day/"


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="plan@test.dev", username="plan", password="x" * 20
    )


@pytest.fixture
def client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


def _task(user, **kw):
    kw.setdefault("priority", 3)
    return Task.objects.create(owner=user, assignee=user, **kw)


class TestPlanDay:
    def test_requires_auth(self):
        assert APIClient().post(URL, {}).status_code in (401, 403)

    def test_empty(self, client):
        r = client.post(URL, {})
        assert r.status_code == 200
        assert r.json()["slots"] == []

    def test_schedules_blocks(self, client, user):
        _task(user, title="A", priority=1)
        _task(user, title="B", priority=4, estimate_hours=2)
        r = client.post(URL, {"start_hour": 9, "date": "2099-01-05"})
        assert r.status_code == 200
        slots = r.json()["slots"]
        assert [s["title"] for s in slots] == ["A", "B"]
        # A: 09:00-10:00 (default 60), B: 10:10-12:10 (estimate 2h + gap)
        assert slots[0]["start"].startswith("2099-01-05T09:00")
        assert slots[1]["start"].startswith("2099-01-05T10:10")
        assert slots[1]["minutes"] == 120
        # persistidos en start_date + version bump
        a = Task.objects.get(title="A")
        assert a.start_date is not None
        assert a.version >= 1

    def test_overdue_first(self, client, user):
        _task(user, title="Overdue", priority=5,
              due_date=timezone.now() - timezone.timedelta(days=2))
        _task(user, title="Later", priority=0)
        r = client.post(URL, {"date": "2099-01-05", "start_hour": 9})
        assert r.json()["slots"][0]["title"] == "Overdue"

    def test_done_states_excluded(self, client, user):
        _task(user, title="Done", state="completed")
        _task(user, title="Open", state="pending")
        r = client.post(URL, {"date": "2099-01-05"})
        assert [s["title"] for s in r.json()["slots"]] == ["Open"]

    def test_limit(self, client, user):
        for i in range(5):
            _task(user, title=f"T{i}")
        r = client.post(URL, {"date": "2099-01-05", "limit": 2})
        assert len(r.json()["slots"]) == 2

    def test_bad_params(self, client):
        assert client.post(URL, {"date": "no-date"}).status_code == 400
        assert client.post(URL, {"start_hour": 99}).status_code == 400
