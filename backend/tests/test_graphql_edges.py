"""Tests de borde para el schema GraphQL: validaciones, filtros y depth limit."""
import pytest
from django.contrib.auth import get_user_model

from apps.graphql_app.schema import _measure_depth, schema
from apps.projects.models import Project
from apps.tags.models import Tag
from apps.tasks.models import Sprint, Task

User = get_user_model()


@pytest.fixture
def user(db):
    u, _ = User.objects.get_or_create(
        username="gql_e", defaults={"email": "gql_e@x.com"}
    )
    return u


class _Info:
    def __init__(self, user):
        self.context = type("Ctx", (), {"user": user})()


def _query(q, user, variables=None):
    class Req:
        pass
    req = Req()
    req.user = user
    return schema.execute(q, context=req, variables=variables or {})


@pytest.mark.django_db
class TestQueryFilters:
    def test_all_tasks_filtro_proyecto(self, user):
        p1 = Project.objects.create(owner=user, name="P1")
        p2 = Project.objects.create(owner=user, name="P2")
        Task.objects.create(owner=user, title="t1", project=p1)
        Task.objects.create(owner=user, title="t2", project=p2)
        r = _query(
            f'{{ allTasks(projectId: {p1.id}) {{ title }} }}', user
        )
        assert not r.errors
        titles = [t["title"] for t in r.data["allTasks"]]
        assert titles == ["t1"]

    def test_all_tasks_filtro_estado(self, user):
        Task.objects.create(owner=user, title="a", state="pending")
        Task.objects.create(owner=user, title="b", state="completed")
        r = _query('{ allTasks(state: "completed") { title } }', user)
        assert [t["title"] for t in r.data["allTasks"]] == ["b"]

    def test_task_por_id(self, user):
        t = Task.objects.create(owner=user, title="x")
        r = _query(f'{{ task(id: {t.id}) {{ title }} }}', user)
        assert r.data["task"]["title"] == "x"

    def test_task_inexistente_null(self, user):
        r = _query('{ task(id: 999999) { title } }', user)
        assert r.data["task"] is None

    def test_project_por_id(self, user):
        p = Project.objects.create(owner=user, name="Proj")
        r = _query(f'{{ project(id: {p.id}) {{ name }} }}', user)
        assert r.data["project"]["name"] == "Proj"

    def test_all_sprints_filtro_proyecto(self, user):
        from django.utils import timezone
        p1 = Project.objects.create(owner=user, name="P1")
        p2 = Project.objects.create(owner=user, name="P2")
        Sprint.objects.create(
            owner=user, project=p1, name="S1",
            start_date=timezone.now().date(), end_date=timezone.now().date(),
        )
        Sprint.objects.create(
            owner=user, project=p2, name="S2",
            start_date=timezone.now().date(), end_date=timezone.now().date(),
        )
        r = _query(
            f'{{ allSprints(projectId: {p1.id}) {{ name }} }}', user
        )
        names = [s["name"] for s in r.data["allSprints"]]
        assert names == ["S1"]

    def test_all_tags_solo_propios(self, user):
        other, _ = User.objects.get_or_create(
            username="gql_e2", defaults={"email": "gql_e2@x.com"}
        )
        Tag.objects.create(owner=user, name="mio")
        Tag.objects.create(owner=other, name="ajeno")
        r = _query('{ allTags { name } }', user)
        names = [t["name"] for t in r.data["allTags"]]
        assert "mio" in names and "ajeno" not in names


@pytest.mark.django_db
class TestCreateMutation:
    def _mut(self, user, **over):
        p = over.pop("project_id", None)
        due = f', dueDate: "{over["due_date"]}"' if over.get("due_date") else ""
        q = (
            f'mutation {{ createTask(title: "{over.get("title", "T")}", projectId: {p}, '
            f'priority: {over.get("priority", 3)}{due}) {{ task {{ title priority }} }} }}'
        )
        return _query(q, user)

    def test_crea_tarea(self, user):
        p = Project.objects.create(owner=user, name="P")
        r = self._mut(user, project_id=p.id, title="Nueva")
        assert not r.errors
        assert r.data["createTask"]["task"]["title"] == "Nueva"
        assert Task.objects.filter(title="Nueva", project=p).exists()

    def test_titulo_strip(self, user):
        p = Project.objects.create(owner=user, name="P")
        r = self._mut(user, project_id=p.id, title="  espacios  ")
        assert not r.errors
        assert Task.objects.get().title == "espacios"

    def test_titulo_vacio_error(self, user):
        p = Project.objects.create(owner=user, name="P")
        r = self._mut(user, project_id=p.id, title="   ")
        assert r.errors

    def test_proyecto_inexistente_error(self, user):
        r = self._mut(user, project_id=999999)
        assert r.errors
        assert "no encontrado" in str(r.errors[0].message).lower()

    def test_prioridad_invalida_error(self, user):
        p = Project.objects.create(owner=user, name="P")
        r = self._mut(user, project_id=p.id, priority=99)
        assert r.errors
        assert "rioridad" in str(r.errors[0].message)

    def test_due_date_invalida_error(self, user):
        p = Project.objects.create(owner=user, name="P")
        r = self._mut(user, project_id=p.id, due_date="no-fecha")
        assert r.errors

    def test_due_date_valida(self, user):
        p = Project.objects.create(owner=user, name="P")
        r = self._mut(
            user, project_id=p.id, due_date="2030-01-15T10:00:00"
        )
        assert not r.errors
        assert Task.objects.get().due_date is not None


@pytest.mark.django_db
class TestUpdateMutation:
    def test_update_title(self, user):
        t = Task.objects.create(owner=user, title="viejo")
        r = _query(
            f'mutation {{ updateTask(id: {t.id}, title: "nuevo") {{ task {{ title }} }} }}',
            user
        )
        assert not r.errors
        t.refresh_from_db()
        assert t.title == "nuevo"

    def test_update_state(self, user):
        t = Task.objects.create(owner=user, title="t", state="pending")
        r = _query(
            f'mutation {{ updateTask(id: {t.id}, state: "completed") {{ task {{ state }} }} }}',
            user
        )
        assert not r.errors
        t.refresh_from_db()
        assert t.state == "completed"

    def test_update_estado_invalido(self, user):
        t = Task.objects.create(owner=user, title="t")
        r = _query(
            f'mutation {{ updateTask(id: {t.id}, state: "inventado") {{ task {{ state }} }} }}',
            user
        )
        assert r.errors
        t.refresh_from_db()
        assert t.state != "inventado"

    def test_update_prioridad_invalida(self, user):
        t = Task.objects.create(owner=user, title="t", priority=3)
        r = _query(
            f'mutation {{ updateTask(id: {t.id}, priority: 42) {{ task {{ priority }} }} }}',
            user
        )
        assert r.errors
        t.refresh_from_db()
        assert t.priority == 3

    def test_update_tarea_inexistente(self, user):
        r = _query(
            'mutation { updateTask(id: 999999, title: "x") { task { id } } }',
            user,
        )
        assert r.errors

    def test_update_titulo_vacio_error(self, user):
        t = Task.objects.create(owner=user, title="orig")
        r = _query(
            f'mutation {{ updateTask(id: {t.id}, title: "   ") {{ task {{ title }} }} }}',
            user
        )
        assert r.errors
        t.refresh_from_db()
        assert t.title == "orig"


@pytest.mark.django_db
class TestDeleteMutation:
    def test_delete(self, user):
        t = Task.objects.create(owner=user, title="t")
        r = _query(
            f'mutation {{ deleteTask(id: {t.id}) {{ success }} }}', user
        )
        assert not r.errors
        assert r.data["deleteTask"]["success"] is True
        assert not Task.objects.filter(id=t.id).exists()

    def test_delete_inexistente(self, user):
        r = _query(
            'mutation { deleteTask(id: 999999) { success } }', user
        )
        assert r.errors


class TestDepthMeasure:
    """_measure_depth: profundidad del selection set."""

    def _depth(self, query):
        from graphql import parse
        doc = parse(query)
        op = doc.definitions[0]
        return _measure_depth(op, {})

    def test_query_plana(self):
        assert self._depth("{ allTasks { id title } }") >= 1

    def test_query_anidada_mide_mas(self):
        shallow = self._depth("{ allTasks { id } }")
        deep = self._depth(
            "{ allTasks { project { tasks: id } sprint { id } } }"
        )
        assert deep > shallow

    def test_fragment_spread_cuenta(self):
        from graphql import parse
        q = """
        query { allTasks { ...F } }
        fragment F on TaskType { project { id } }
        """
        doc = parse(q)
        op = doc.definitions[0]
        frags = {d.name.value: d for d in doc.definitions[1:]}
        depth_con_frag = _measure_depth(op, frags)
        depth_sin = _measure_depth(op, {})
        assert depth_con_frag >= depth_sin
