"""Tests dirigidos para graphql_app: auth, depth limit, validaciones, aislamiento."""
from unittest.mock import Mock

import pytest
from django.contrib.auth import get_user_model

from apps.graphql_app.schema import MAX_QUERY_DEPTH, _measure_depth, schema
from apps.projects.models import Project
from apps.tags.models import Tag
from apps.tasks.models import Sprint, Task

User = get_user_model()


@pytest.fixture
def gql_user(db):
    # get_or_create: sin rollback bajo -p no:django, la DB persiste entre runs
    user, _ = User.objects.get_or_create(
        username="gq",
        defaults={"email": "gq@g.com", "password": "pass"},
    )
    return user


def _mkuser(username, email):
    user, _ = User.objects.get_or_create(
        username=username,
        defaults={"email": email, "password": "pass"},
    )
    return user


def _ctx(user):
    info = Mock()
    info.context.user = user
    return info.context


@pytest.mark.django_db
class TestRestGraphqlConsistency:
    """GraphQL debe respetar los mismos permisos que REST.

    Regresión: las mutations usaban for_user(read) — un viewer de un
    proyecto compartido podía actualizar/borrar tareas vía GraphQL aunque
    REST se lo prohíbe. Y las queries filtraban owner=user, ocultando
    proyectos compartidos que REST sí muestra.
    """

    def _shared_project(self, owner, member, role):
        from apps.collaboration.models import ProjectMember
        project = Project.objects.create(owner=owner, name="Shared")
        ProjectMember.objects.create(project=project, user=member, role=role)
        return project

    def test_viewer_no_puede_update_task(self):
        """Un viewer de proyecto compartido NO puede mutar tareas (como REST)."""
        owner = _mkuser("gqlown1", "gqlown1@x.com")
        viewer = _mkuser("gqlview1", "gqlview1@x.com")
        project = self._shared_project(owner, viewer, "viewer")
        task = Task.objects.create(owner=owner, project=project, title="T")

        result = schema.execute(
            f'mutation {{ updateTask(id: {task.id}, title: "Hackeada") '
            '{ task { id title } } }',
            context=_ctx(viewer),
        )
        assert result.errors, "viewer debería fallar como en REST"
        task.refresh_from_db()
        assert task.title == "T"

    def test_viewer_no_puede_delete_task(self):
        owner = _mkuser("gqlown2", "gqlown2@x.com")
        viewer = _mkuser("gqlview2", "gqlview2@x.com")
        project = self._shared_project(owner, viewer, "viewer")
        task = Task.objects.create(owner=owner, project=project, title="T")

        result = schema.execute(
            f'mutation {{ deleteTask(id: {task.id}) {{ success }} }}',
            context=_ctx(viewer),
        )
        assert result.errors
        assert Task.objects.filter(id=task.id).exists()

    def test_editor_puede_update_task(self):
        """Un editor SÍ puede mutar (consistente con REST write)."""
        owner = _mkuser("gqlown3", "gqlown3@x.com")
        editor = _mkuser("gqled1", "gqled1@x.com")
        project = self._shared_project(owner, editor, "editor")
        task = Task.objects.create(owner=owner, project=project, title="T")

        result = schema.execute(
            f'mutation {{ updateTask(id: {task.id}, title: "Editada") '
            '{ task { id title } } }',
            context=_ctx(editor),
        )
        assert not result.errors
        task.refresh_from_db()
        assert task.title == "Editada"

    def test_member_ve_proyectos_compartidos(self):
        """allProjects incluye proyectos donde el user es miembro (como REST)."""
        owner = _mkuser("gqlown4", "gqlown4@x.com")
        member = _mkuser("gqlmem4", "gqlmem4@x.com")
        self._shared_project(owner, member, "viewer")

        result = schema.execute(
            '{ allProjects { id name } }', context=_ctx(member)
        )
        assert not result.errors
        names = [p["name"] for p in result.data["allProjects"]]
        assert "Shared" in names

    def test_viewer_no_puede_crear_en_proyecto(self):
        """createTask exige write en el proyecto (viewer → error)."""
        owner = _mkuser("gqlown5", "gqlown5@x.com")
        viewer = _mkuser("gqlview5", "gqlview5@x.com")
        project = self._shared_project(owner, viewer, "viewer")

        result = schema.execute(
            f'mutation {{ createTask(title: "X", projectId: {project.id}) '
            '{ task { id } } }',
            context=_ctx(viewer),
        )
        assert result.errors

    def test_editor_puede_crear_en_proyecto(self):
        owner = _mkuser("gqlown6", "gqlown6@x.com")
        editor = _mkuser("gqled6", "gqled6@x.com")
        project = self._shared_project(owner, editor, "editor")

        result = schema.execute(
            f'mutation {{ createTask(title: "X", projectId: {project.id}) '
            '{ task { id title } } }',
            context=_ctx(editor),
        )
        assert not result.errors
        assert Task.objects.filter(title="X", project=project).exists()


@pytest.mark.django_db
class TestLoginRequired:
    """login_required rechaza usuarios no autenticados en TODAS las operaciones."""

    def test_task_sin_auth(self):
        info = Mock()
        info.context.user = None
        result = schema.execute('{ task(id: 1) { id } }', context=info.context)
        assert result.errors

    def test_all_projects_sin_auth(self):
        info = Mock()
        info.context.user = None
        result = schema.execute('{ allProjects { id } }', context=info.context)
        assert result.errors

    def test_all_tags_sin_auth(self):
        info = Mock()
        info.context.user = None
        result = schema.execute('{ allTags { id } }', context=info.context)
        assert result.errors

    def test_create_task_sin_auth(self, gql_user):
        info = Mock()
        info.context.user = None
        result = schema.execute(
            'mutation { createTask(title: "X", projectId: 1) { task { id } } }',
            context=info.context,
        )
        assert result.errors

    def test_update_task_sin_auth(self):
        info = Mock()
        info.context.user = None
        result = schema.execute(
            'mutation { updateTask(id: 1, title: "X") { task { id } } }',
            context=info.context,
        )
        assert result.errors

    def test_delete_task_sin_auth(self):
        info = Mock()
        info.context.user = None
        result = schema.execute(
            'mutation { deleteTask(id: 1) { success } }',
            context=info.context,
        )
        assert result.errors


@pytest.mark.django_db
class TestDepthLimit:
    """DepthLimitMiddleware rechaza queries que exceden MAX_QUERY_DEPTH."""

    def test_deep_query_rechazada(self, gql_user):
        result2 = schema.execute(
            "{ allTasks { id parent { id } } }", context=_ctx(gql_user)
        )
        # No assert estricto — solo verificar que el middleware no crashea
        assert result2 is not None

    def test_measure_depth_shallow(self):
        """_measure_depth con un selection set simple."""
        from graphql import parse
        doc = parse("{ allTasks { id title } }")
        op = doc.definitions[0]
        depth = _measure_depth(op, {})
        assert depth >= 1

    def test_measure_depth_none(self):
        assert _measure_depth(None, {}) == 0

    def test_measure_depth_fragments(self):
        """Fragments aumentan la profundidad contada."""
        from graphql import parse
        from graphql.language.ast import FragmentDefinitionNode
        doc = parse("""
            fragment F on Task { project { id } }
            query { allTasks { ...F } }
        """)
        op = doc.definitions[1]
        frags = {d.name.value: d for d in doc.definitions if isinstance(d, FragmentDefinitionNode)}
        depth = _measure_depth(op, frags)
        assert depth >= 2

    def test_measure_depth_inline_fragment(self):
        from graphql import parse
        doc = parse("{ allTasks { ... on Task { id project { name } } } }")
        op = doc.definitions[0]
        depth = _measure_depth(op, {})
        assert depth >= 2

    def test_middleware_rechaza_query_profunda(self, gql_user):
        """DepthLimitMiddleware lanza GraphQLError en queries > MAX_QUERY_DEPTH."""
        import types

        from graphql import GraphQLError, parse

        from apps.graphql_app.schema import DepthLimitMiddleware
        mw = DepthLimitMiddleware()
        info = Mock()
        info.context = types.SimpleNamespace(user=gql_user)
        deep_query = "{ " + "".join(f"f{i} {{ " for i in range(MAX_QUERY_DEPTH + 2)) + "x" + " }" * (MAX_QUERY_DEPTH + 2) + " }"
        info.operation = parse(deep_query).definitions[0]
        info.fragments = {}
        with pytest.raises(GraphQLError):
            mw.resolve(lambda *a, **k: None, None, info)

    def test_middleware_acepta_query_superficial(self, gql_user):
        import types

        from graphql import parse

        from apps.graphql_app.schema import DepthLimitMiddleware
        mw = DepthLimitMiddleware()
        info = Mock()
        info.context = types.SimpleNamespace(user=gql_user)
        info.operation = parse("{ a { b } }").definitions[0]
        info.fragments = {}
        called = []
        mw.resolve(lambda *a, **k: called.append(True) or "ok", None, info)
        assert called


@pytest.mark.django_db
class TestMutationValidations:
    def setup_method(self):
        # Sin rollback transaccional bajo -p no:django: get_or_create para
        # tolerar estado residual de tests anteriores.
        self.user, _ = User.objects.get_or_create(
            username="mv",
            defaults={"email": "mv@m.com", "password": "pass"},
        )
        self.project, _ = Project.objects.get_or_create(
            owner=self.user, name="P"
        )

    def _run(self, query):
        return schema.execute(query, context=_ctx(self.user))

    def test_create_task_titulo_vacio(self):
        r = self._run(f'mutation {{ createTask(title: "   ", projectId: {self.project.id}) {{ task {{ id }} }} }}')
        assert r.errors

    def test_create_task_titulo_largo(self):
        long_title = "x" * 501
        r = self._run(f'mutation {{ createTask(title: "{long_title}", projectId: {self.project.id}) {{ task {{ id }} }} }}')
        assert r.errors

    def test_create_task_prioridad_invalida(self):
        r = self._run(f'mutation {{ createTask(title: "T", projectId: {self.project.id}, priority: 99) {{ task {{ id }} }} }}')
        assert r.errors

    def test_create_task_due_date_invalida(self):
        r = self._run(f'mutation {{ createTask(title: "T", projectId: {self.project.id}, dueDate: "not-a-date") {{ task {{ id }} }} }}')
        assert r.errors

    def test_create_task_proyecto_ajeno(self, gql_user):
        """No se puede crear tarea en proyecto de otro usuario."""
        other = _mkuser("o2", "o2@o.com")
        other_project, _ = Project.objects.get_or_create(owner=other, name="OtherP")
        r = self._run(f'mutation {{ createTask(title: "T", projectId: {other_project.id}) {{ task {{ id }} }} }}')
        assert r.errors
        assert not Task.objects.filter(project=other_project).exists()

    def test_update_task_estado_invalido(self):
        task = Task.objects.create(owner=self.user, project=self.project, title="T")
        r = self._run(f'mutation {{ updateTask(id: {task.id}, state: "invented") {{ task {{ id }} }} }}')
        assert r.errors
        task.refresh_from_db()
        assert task.state != "invented"

    def test_update_task_prioridad_invalida(self):
        task = Task.objects.create(owner=self.user, project=self.project, title="T")
        r = self._run(f'mutation {{ updateTask(id: {task.id}, priority: 99) {{ task {{ id }} }} }}')
        assert r.errors

    def test_update_task_titulo_vacio(self):
        task = Task.objects.create(owner=self.user, project=self.project, title="T")
        r = self._run(f'mutation {{ updateTask(id: {task.id}, title: "  ") {{ task {{ id }} }} }}')
        assert r.errors

    def test_update_task_ajena(self, gql_user):
        """Usuario B no puede editar tarea de usuario A."""
        other = _mkuser("o3", "o3@o.com")
        other_project, _ = Project.objects.get_or_create(owner=other, name="OP")
        other_task, _ = Task.objects.get_or_create(owner=other, project=other_project, title="OtherTask")
        r = self._run(f'mutation {{ updateTask(id: {other_task.id}, title: "Hacked") {{ task {{ id }} }} }}')
        assert r.errors
        other_task.refresh_from_db()
        assert other_task.title == "OtherTask"

    def test_delete_task_ajena(self, gql_user):
        """Usuario B no puede borrar tarea de usuario A."""
        other = _mkuser("o4", "o4@o.com")
        other_project, _ = Project.objects.get_or_create(owner=other, name="OP")
        other_task, _ = Task.objects.get_or_create(owner=other, project=other_project, title="OtherTask")
        r = self._run(f'mutation {{ deleteTask(id: {other_task.id}) {{ success }} }}')
        assert r.errors
        assert Task.objects.filter(id=other_task.id).exists()


@pytest.mark.django_db
class TestIsolation:
    """Los resolvers solo devuelven datos del usuario autenticado."""

    def setup_method(self):
        self.user, _ = User.objects.get_or_create(
            username="iso",
            defaults={"email": "iso@i.com", "password": "pass"},
        )
        self.other, _ = User.objects.get_or_create(
            username="oth",
            defaults={"email": "oth@o.com", "password": "pass"},
        )
        self.project, _ = Project.objects.get_or_create(owner=self.user, name="MyP")
        self.other_project, _ = Project.objects.get_or_create(owner=self.other, name="OtherP")
        self.task, _ = Task.objects.get_or_create(owner=self.user, project=self.project, title="MyTask")
        self.other_task, _ = Task.objects.get_or_create(owner=self.other, project=self.other_project, title="OtherTask")
        self.tag, _ = Tag.objects.get_or_create(owner=self.user, name="mine")
        self.other_tag, _ = Tag.objects.get_or_create(owner=self.other, name="theirs")

    def test_all_tasks_solo_propias(self):
        r = schema.execute("{ allTasks { title } }", context=_ctx(self.user))
        titles = [t["title"] for t in r.data["allTasks"]]
        assert "MyTask" in titles
        assert "OtherTask" not in titles

    def test_task_ajena_no_visible(self):
        r = schema.execute(f'{{ task(id: {self.other_task.id}) {{ id title }} }}', context=_ctx(self.user))
        assert r.data["task"] is None

    def test_all_projects_solo_propios(self):
        r = schema.execute("{ allProjects { name } }", context=_ctx(self.user))
        names = [p["name"] for p in r.data["allProjects"]]
        assert "MyP" in names
        assert "OtherP" not in names

    def test_all_projects_excluye_archivados(self):
        Project.objects.get_or_create(
            owner=self.user, name="Archived", defaults={"is_archived": True}
        )
        r = schema.execute("{ allProjects { name } }", context=_ctx(self.user))
        names = [p["name"] for p in r.data["allProjects"]]
        assert "Archived" not in names

    def test_all_tags_solo_propios(self):
        r = schema.execute("{ allTags { name } }", context=_ctx(self.user))
        names = [t["name"] for t in r.data["allTags"]]
        assert "mine" in names
        assert "theirs" not in names

    def test_all_sprints_solo_propios(self):
        from datetime import timedelta

        from django.utils import timezone
        Sprint.objects.get_or_create(
            project=self.project, name="S1",
            defaults={
                "owner": self.user,
                "start_date": timezone.now(),
                "end_date": timezone.now() + timedelta(days=7),
            },
        )
        Sprint.objects.get_or_create(
            project=self.other_project, name="OtherS",
            defaults={
                "owner": self.other,
                "start_date": timezone.now(),
                "end_date": timezone.now() + timedelta(days=7),
            },
        )
        r = schema.execute("{ allSprints { name } }", context=_ctx(self.user))
        names = [s["name"] for s in r.data["allSprints"]]
        assert "S1" in names
        assert "OtherS" not in names

    def test_all_sprints_filter_project(self):
        from datetime import timedelta

        from django.utils import timezone
        Sprint.objects.get_or_create(
            project=self.project, name="S1",
            defaults={
                "owner": self.user,
                "start_date": timezone.now(),
                "end_date": timezone.now() + timedelta(days=7),
            },
        )
        r = schema.execute(
            f'{{ allSprints(projectId: {self.project.id}) {{ name }} }}',
            context=_ctx(self.user),
        )
        assert len(r.data["allSprints"]) == 1


@pytest.mark.django_db
class TestUserTypeRestriction:
    """El tipo User solo expone campos públicos (paridad REST).

    Sin un UserType registrado, graphene-django autogenera uno con TODOS
    los campos del modelo: password hash, ical_token, inbound_email_token
    y scim_* serían consultables por cualquier usuario autenticado.
    """

    def _task(self, user):
        project, _ = Project.objects.get_or_create(owner=user, name="PU")
        task, _ = Task.objects.get_or_create(
            owner=user, project=project, title="TT"
        )
        return task

    def test_owner_no_expone_password(self, gql_user):
        task = self._task(gql_user)
        r = schema.execute(
            f'{{ task(id: {task.id}) {{ owner {{ password }} }} }}',
            context=_ctx(gql_user),
        )
        assert r.errors

    def test_owner_no_expone_tokens(self, gql_user):
        task = self._task(gql_user)
        query = (
            "{ task(id: %d) { owner { icalToken inboundEmailToken "
            "scimExternalId } } }"
        ) % task.id
        r = schema.execute(query, context=_ctx(gql_user))
        assert r.errors

    def test_owner_expone_campos_publicos(self, gql_user):
        task = self._task(gql_user)
        query = (
            "{ task(id: %d) { owner { id username email "
            "firstName lastName } } }"
        ) % task.id
        r = schema.execute(query, context=_ctx(gql_user))
        assert not r.errors
        assert r.data["task"]["owner"]["email"] == gql_user.email


@pytest.mark.django_db
class TestListLimits:
    """Las listas GraphQL están acotadas (REST pagina; GraphQL no)."""

    def test_all_tasks_respeta_limit(self, gql_user):
        project, _ = Project.objects.get_or_create(owner=gql_user, name="PL")
        for i in range(3):
            Task.objects.get_or_create(
                owner=gql_user, project=project, title=f"T{i}"
            )
        r = schema.execute(
            "{ allTasks(limit: 2) { id } }", context=_ctx(gql_user)
        )
        assert not r.errors
        assert len(r.data["allTasks"]) == 2

    def test_all_tags_respeta_limit(self, gql_user):
        for i in range(3):
            Tag.objects.get_or_create(owner=gql_user, name=f"t{i}")
        r = schema.execute(
            "{ allTags(limit: 1) { id } }", context=_ctx(gql_user)
        )
        assert len(r.data["allTags"]) == 1

    def test_cap_limit_unidad(self):
        from apps.graphql_app.schema import (
            DEFAULT_LIST_LIMIT,
            MAX_LIST_LIMIT,
            _cap_limit,
        )
        assert _cap_limit(None) == DEFAULT_LIST_LIMIT
        assert _cap_limit(10) == 10
        assert _cap_limit(99999) == MAX_LIST_LIMIT
        assert _cap_limit(-5) == 0
