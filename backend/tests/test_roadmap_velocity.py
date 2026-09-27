"""Tests para roadmap (timeline) y velocity endpoints."""
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.tasks.advanced_metrics import get_roadmap_data, get_velocity_data
from apps.tasks.models import Epic, Sprint, Task, TimeEntry

User = get_user_model()


@pytest.fixture
def user(db):
    u, _ = User.objects.get_or_create(
        username="rm_user", defaults={"email": "rm@x.com"}
    )
    return u


@pytest.mark.django_db
class TestRoadmap:
    def test_epic_con_progreso(self, user):
        epic = Epic.objects.create(owner=user, title="E1", color="#ff0000")
        Task.objects.create(owner=user, title="T1", epic=epic, state="completed")
        Task.objects.create(owner=user, title="T2", epic=epic, state="pending")
        data = get_roadmap_data(user)
        lane = data["epics"][0]
        assert lane["title"] == "E1"
        assert lane["total"] == 2
        assert lane["done"] == 1
        assert lane["progress"] == 50.0

    def test_epic_usa_fechas_propias(self, user):
        Epic.objects.create(
            owner=user, title="E1",
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=30),
        )
        data = get_roadmap_data(user)
        lane = data["epics"][0]
        assert lane["start"] == timezone.now().date().isoformat()
        assert lane["end"] is not None

    def test_epic_infiere_fechas_de_tareas(self, user):
        epic = Epic.objects.create(owner=user, title="E1")
        t = Task.objects.create(
            owner=user, title="T", epic=epic,
            due_date=timezone.now() + timedelta(days=10),
        )
        data = get_roadmap_data(user)
        lane = data["epics"][0]
        assert lane["end"] == t.due_date.isoformat()

    def test_milestones_sprints(self, user):
        Sprint.objects.create(
            owner=user, name="S1",
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=14),
        )
        data = get_roadmap_data(user)
        assert len(data["milestones"]) == 1
        assert data["milestones"][0]["name"] == "S1"

    def test_no_ve_epicas_ajenas(self, user):
        other, _ = User.objects.get_or_create(
            username="rm_o", defaults={"email": "rm_o@x.com"}
        )
        Epic.objects.create(owner=other, title="Ajena")
        data = get_roadmap_data(user)
        assert data["epics"] == []

    def test_endpoint(self, authed_client, user):
        Epic.objects.create(owner=user, title="E1")
        resp = authed_client.get("/api/tasks/roadmap/")
        assert resp.status_code == 200
        assert "epics" in resp.json()
        assert "milestones" in resp.json()


@pytest.mark.django_db
class TestVelocity:
    def test_velocity_por_sprint(self, user):
        sprint = Sprint.objects.create(
            owner=user, name="S1",
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=14),
        )
        Task.objects.create(
            owner=user, title="T1", sprint=sprint,
            state="completed", story_points=5,
        )
        Task.objects.create(
            owner=user, title="T2", sprint=sprint,
            state="pending", story_points=3,
        )
        data = get_velocity_data(user)
        v = data["velocity"][0]
        assert v["completed_points"] == 5
        assert v["completed_tasks"] == 1

    def test_estimado_vs_real(self, user):
        sprint = Sprint.objects.create(
            owner=user, name="S1",
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=14),
        )
        task = Task.objects.create(
            owner=user, title="T1", sprint=sprint,
            state="completed", estimate_hours=8,
        )
        TimeEntry.objects.create(task=task, user=user, duration_seconds=14400)  # 4h
        data = get_velocity_data(user)
        eva = data["estimated_vs_actual"][0]
        assert eva["estimated_hours"] == 8.0
        assert eva["actual_hours"] == 4.0

    def test_endpoint(self, authed_client, user):
        resp = authed_client.get("/api/tasks/velocity/")
        assert resp.status_code == 200
        assert "velocity" in resp.json()
        assert "estimated_vs_actual" in resp.json()
