"""Tests de regresión N+1: el número de queries no debe crecer con N.

Crea el mismo escenario con 3 y con 10 tareas y comprueba que el
conteo de queries del listado es (casi) constante.
"""
import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.projects.models import Project
from apps.tags.models import Tag
from apps.tasks.models import Comment, Sprint, Subtask, Task, TaskActivity

User = get_user_model()


def _client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


def _seed(user, n):
    """Crea n tareas con relaciones que el serializer serializa."""
    p = Project.objects.create(owner=user, name=f"P{n}")
    s = Sprint.objects.create(
        owner=user, name=f"S{n}", project=p,
        start_date="2024-01-01", end_date="2024-01-14",
    )
    tag = Tag.objects.create(owner=user, name=f"tag{n}")
    for i in range(n):
        t = Task.objects.create(
            owner=user, title=f"t{i}", project=p, sprint=s, priority=i % 6,
        )
        t.tags.add(tag)
        Comment.objects.create(task=t, author=user, body="c")
        Subtask.objects.create(task=t, title="st")
        TaskActivity.objects.create(
            task=t, actor=user, action="created"
        )
        Task.objects.create(owner=user, title=f"child{i}", parent=t)


def _count_queries(client, url):
    with CaptureQueriesContext(connection) as ctx:
        resp = client.get(url)
        assert resp.status_code == 200
    return len(ctx.captured_queries)


@pytest.mark.django_db
class TestNPlusOne:
    def test_tasks_list_queries_constantes(self):
        u1, _ = User.objects.get_or_create(
            username="n1_a", defaults={"email": "n1_a@x.com"}
        )
        _seed(u1, 3)
        q3 = _count_queries(_client(u1), "/api/tasks/")

        u2, _ = User.objects.get_or_create(
            username="n1_b", defaults={"email": "n1_b@x.com"}
        )
        _seed(u2, 10)
        q10 = _count_queries(_client(u2), "/api/tasks/")

        # El crecimiento debe ser acotado (no lineal con N).
        # Paginación por defecto puede influir; permitimos un margen.
        assert q10 - q3 <= 5, f"3→{q3} queries, 10→{q10} queries"

    def test_sprints_list_queries_constantes(self):
        u1, _ = User.objects.get_or_create(
            username="n1_c", defaults={"email": "n1_c@x.com"}
        )
        for i in range(3):
            s = Sprint.objects.create(
                owner=u1, name=f"s{i}",
                start_date="2024-01-01", end_date="2024-01-14",
            )
            Task.objects.create(owner=u1, title=f"t{i}", sprint=s)
        q3 = _count_queries(_client(u1), "/api/sprints/")

        u2, _ = User.objects.get_or_create(
            username="n1_d", defaults={"email": "n1_d@x.com"}
        )
        for i in range(10):
            s = Sprint.objects.create(
                owner=u2, name=f"s{i}",
                start_date="2024-01-01", end_date="2024-01-14",
            )
            Task.objects.create(owner=u2, title=f"t{i}", sprint=s)
        q10 = _count_queries(_client(u2), "/api/sprints/")
        assert q10 - q3 <= 5, f"3→{q3} queries, 10→{q10} queries"

    def test_projects_list_queries_constantes(self):
        u1, _ = User.objects.get_or_create(
            username="n1_e", defaults={"email": "n1_e@x.com"}
        )
        for i in range(3):
            p = Project.objects.create(owner=u1, name=f"p{i}")
            Task.objects.create(owner=u1, title=f"t{i}", project=p)
        q3 = _count_queries(_client(u1), "/api/projects/")

        u2, _ = User.objects.get_or_create(
            username="n1_f", defaults={"email": "n1_f@x.com"}
        )
        for i in range(10):
            p = Project.objects.create(owner=u2, name=f"p{i}")
            Task.objects.create(owner=u2, title=f"t{i}", project=p)
        q10 = _count_queries(_client(u2), "/api/projects/")
        assert q10 - q3 <= 5, f"3→{q3} queries, 10→{q10} queries"

    def test_epics_list_queries_constantes(self):
        from apps.tasks.models import Epic
        u1, _ = User.objects.get_or_create(
            username="n1_i", defaults={"email": "n1_i@x.com"}
        )
        for i in range(3):
            e = Epic.objects.create(owner=u1, title=f"e{i}")
            Task.objects.create(owner=u1, title=f"t{i}", epic=e,
                                state="completed" if i == 0 else "pending")
        q3 = _count_queries(_client(u1), "/api/epics/")

        u2, _ = User.objects.get_or_create(
            username="n1_j", defaults={"email": "n1_j@x.com"}
        )
        for i in range(10):
            e = Epic.objects.create(owner=u2, title=f"e{i}")
            Task.objects.create(owner=u2, title=f"t{i}", epic=e)
        q10 = _count_queries(_client(u2), "/api/epics/")
        assert q10 - q3 <= 5, f"3→{q3} queries, 10→{q10} queries"

    def test_comments_list_queries_constantes(self):
        u1, _ = User.objects.get_or_create(
            username="n1_g", defaults={"email": "n1_g@x.com"}
        )
        t1 = Task.objects.create(owner=u1, title="t")
        for i in range(3):
            Comment.objects.create(task=t1, author=u1, body=f"c{i}")
        q3 = _count_queries(_client(u1), "/api/comments/")

        u2, _ = User.objects.get_or_create(
            username="n1_h", defaults={"email": "n1_h@x.com"}
        )
        t2 = Task.objects.create(owner=u2, title="t")
        for i in range(10):
            Comment.objects.create(task=t2, author=u2, body=f"c{i}")
        q10 = _count_queries(_client(u2), "/api/comments/")
        assert q10 - q3 <= 5, f"3→{q3} queries, 10→{q10} queries"
