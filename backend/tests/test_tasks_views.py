from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.projects.models import Project
from apps.tasks.models import (
    Comment,
    Epic,
    Sprint,
    Subtask,
    Task,
    TaskActivity,
    TaskRelation,
)

User = get_user_model()


@pytest.mark.django_db
class TestTaskViewSet:
    @pytest.fixture(autouse=True)
    def setup_data(self, db):
        self.user = User.objects.create_user(username="tv", email="tv@tv.com", password="pass")
        self.other = User.objects.create_user(username="tv2", email="tv2@tv.com", password="pass")
        self.project = Project.objects.create(owner=self.user, name="P1")
        self.client = APIClient()
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

    def test_list_filter_due_before(self):
        Task.objects.create(owner=self.user, title="T1", due_date=timezone.now() - timedelta(days=5))
        Task.objects.create(owner=self.user, title="T2", due_date=timezone.now() + timedelta(days=5))
        resp = self.client.get("/api/tasks/?due_before=2020-01-01")
        assert resp.status_code == 200
        assert len(resp.data) == 0
        resp = self.client.get("/api/tasks/?due_before=2030-01-01")
        assert len(resp.data) == 2

    def test_list_filter_due_after(self):
        Task.objects.create(owner=self.user, title="T1", due_date=timezone.now() - timedelta(days=5))
        Task.objects.create(owner=self.user, title="T2", due_date=timezone.now() + timedelta(days=5))
        resp = self.client.get("/api/tasks/?due_after=2020-01-01")
        assert len(resp.data) == 2

    def test_list_filter_active_sprint(self):
        sprint = Sprint.objects.create(owner=self.user, name="S1", state="active", start_date=timezone.now().date(), end_date=timezone.now().date() + timedelta(days=14))
        Task.objects.create(owner=self.user, title="T1", sprint=sprint)
        Task.objects.create(owner=self.user, title="T2")
        resp = self.client.get("/api/tasks/?active_sprint=true")
        assert len(resp.data) == 1

    def test_list_filter_epic(self):
        epic = Epic.objects.create(owner=self.user, title="E1", project=self.project)
        Task.objects.create(owner=self.user, title="T1", epic=epic)
        Task.objects.create(owner=self.user, title="T2")
        resp = self.client.get(f"/api/tasks/?epic_id={epic.id}")
        assert len(resp.data) == 1

    def test_create_task(self):
        resp = self.client.post("/api/tasks/", {"title": "New", "project": self.project.id})
        assert resp.status_code == 201
        assert Task.objects.filter(title="New", owner=self.user).exists()

    def test_update_task_state_change(self):
        task = Task.objects.create(owner=self.user, title="T", state="pending")
        resp = self.client.patch(f"/api/tasks/{task.id}/", {"state": "in_progress"})
        assert resp.status_code == 200
        task.refresh_from_db()
        assert task.state == "in_progress"
        assert TaskActivity.objects.filter(task=task, action="state_changed").exists()

    def test_update_task_completed(self):
        task = Task.objects.create(owner=self.user, title="T", state="pending")
        resp = self.client.patch(f"/api/tasks/{task.id}/", {"state": "completed"})
        assert resp.status_code == 200
        task.refresh_from_db()
        assert task.state == "completed"
        assert task.completed_at is not None

    def test_update_task_uncomplete(self):
        task = Task.objects.create(owner=self.user, title="T", state="completed", completed_at=timezone.now())
        resp = self.client.patch(f"/api/tasks/{task.id}/", {"state": "pending"})
        assert resp.status_code == 200
        task.refresh_from_db()
        assert task.completed_at is None

    def test_add_subtask(self):
        task = Task.objects.create(owner=self.user, title="T")
        resp = self.client.post(f"/api/tasks/{task.id}/subtasks/", {"title": "Sub"})
        assert resp.status_code == 201
        assert Subtask.objects.filter(task=task, title="Sub").exists()
        assert TaskActivity.objects.filter(task=task, action="subtask_added").exists()

    def test_add_comment(self):
        task = Task.objects.create(owner=self.user, title="T")
        resp = self.client.post(f"/api/tasks/{task.id}/comments/", {"body": "Comment"})
        assert resp.status_code == 201
        assert Comment.objects.filter(task=task, body="Comment").exists()
        assert TaskActivity.objects.filter(task=task, action="commented").exists()

    def test_activities(self):
        task = Task.objects.create(owner=self.user, title="T")
        TaskActivity.objects.create(task=task, actor=self.user, action="state_changed")
        resp = self.client.get(f"/api/tasks/{task.id}/activities/")
        assert resp.status_code == 200
        assert len(resp.data) == 1

    def test_relations_get(self):
        task = Task.objects.create(owner=self.user, title="T")
        target = Task.objects.create(owner=self.user, title="T2")
        TaskRelation.objects.create(source=task, target=target, relation_type="depends_on")
        resp = self.client.get(f"/api/tasks/{task.id}/relations/")
        assert resp.status_code == 200
        assert len(resp.data) == 1

    def test_relations_post(self):
        task = Task.objects.create(owner=self.user, title="T")
        target = Task.objects.create(owner=self.user, title="T2")
        resp = self.client.post(f"/api/tasks/{task.id}/relations/", {"target": target.id, "relation_type": "depends_on"})
        assert resp.status_code == 201
        assert TaskRelation.objects.filter(source=task, target=target).exists()

    def test_relations_post_invalid_target(self):
        task = Task.objects.create(owner=self.user, title="T")
        other_task = Task.objects.create(owner=self.other, title="T2")
        resp = self.client.post(f"/api/tasks/{task.id}/relations/", {"target": other_task.id, "relation_type": "depends_on"})
        assert resp.status_code == 400

    def test_move_to_sprint(self):
        task = Task.objects.create(owner=self.user, title="T")
        sprint = Sprint.objects.create(owner=self.user, name="S1", state="active", start_date=timezone.now().date(), end_date=timezone.now().date() + timedelta(days=14))
        resp = self.client.post(f"/api/tasks/{task.id}/move_to_sprint/", {"sprint_id": sprint.id})
        assert resp.status_code == 200
        task.refresh_from_db()
        assert task.sprint == sprint

    def test_move_to_sprint_not_found(self):
        task = Task.objects.create(owner=self.user, title="T")
        resp = self.client.post(f"/api/tasks/{task.id}/move_to_sprint/", {"sprint_id": 999})
        assert resp.status_code == 404

    def test_bulk_update(self):
        t1 = Task.objects.create(owner=self.user, title="T1")
        t2 = Task.objects.create(owner=self.user, title="T2")
        resp = self.client.post("/api/tasks/bulk_update/", {"task_ids": [t1.id, t2.id], "updates": {"priority": 1}}, format="json")
        assert resp.status_code == 200
        assert resp.data["updated"] == 2
        t1.refresh_from_db()
        assert t1.priority == 1

    def test_bulk_update_empty(self):
        resp = self.client.post("/api/tasks/bulk_update/", {"task_ids": [], "updates": {}}, format="json")
        assert resp.status_code == 400

    def test_bulk_delete(self):
        t1 = Task.objects.create(owner=self.user, title="T1")
        t2 = Task.objects.create(owner=self.user, title="T2")
        resp = self.client.post("/api/tasks/bulk_delete/", {"task_ids": [t1.id, t2.id]}, format="json")
        assert resp.status_code == 200
        assert resp.data["deleted"] == 2
        assert not Task.objects.filter(id__in=[t1.id, t2.id]).exists()

    def test_bulk_move_sprint(self):
        sprint = Sprint.objects.create(owner=self.user, name="S1", state="active", start_date=timezone.now().date(), end_date=timezone.now().date() + timedelta(days=14))
        t1 = Task.objects.create(owner=self.user, title="T1")
        resp = self.client.post("/api/tasks/bulk_move_sprint/", {"task_ids": [t1.id], "sprint_id": sprint.id}, format="json")
        assert resp.status_code == 200
        t1.refresh_from_db()
        assert t1.sprint == sprint

    def test_search(self):
        Task.objects.create(owner=self.user, title="Bug fix", description="Fix the bug")
        Task.objects.create(owner=self.user, title="Feature", description="Add feature")
        resp = self.client.get("/api/tasks/search/?q=bug")
        assert resp.status_code == 200
        assert resp.data["count"] == 1
        assert resp.data["results"][0]["title"] == "Bug fix"

    def test_search_empty(self):
        resp = self.client.get("/api/tasks/search/?q=")
        assert resp.status_code == 200
        assert resp.data["count"] == 0
