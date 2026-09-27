"""Fixtures compartidas para los tests del backend."""
import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.projects.models import Project
from apps.tags.models import Tag
from apps.tasks.models import Task

User = get_user_model()


@pytest.fixture(autouse=True)
def _db_isolation(request):
    """Envuelve CADA test en transaction.atomic + rollback.

    Debe ser autouse: los tests con ``setup_method`` (xunit) ejecutan su
    setup dentro de ``_xunit_setup_method_fixture``, que se resuelve ANTES
    que los fixtures explícitos. Si el atomic lo abre el fixture ``db``
    (explícito), los objetos creados en ``setup_method`` quedan fuera de la
    transacción y COMMITEAN — fugan a los tests siguientes.
    """
    if request.config.pluginmanager.has_plugin("django"):
        yield
        return
    from django.db import connections, transaction

    atomics = []
    for alias in connections:
        conn = connections[alias]
        if not getattr(conn.features, "supports_transactions", False):
            continue
        atomic = transaction.atomic(using=alias)
        atomic.__enter__()
        atomics.append((conn, atomic))
    try:
        yield
    finally:
        for conn, atomic in reversed(atomics):
            conn.set_rollback(True)
            atomic.__exit__(None, None, None)


@pytest.fixture
def db(request):
    """Proporciona acceso a la base de datos de test.

    La transacción la abre ``_db_isolation`` (autouse). Aquí solo queda el
    desbloqueo de pytest-django y el mail outbox de SimpleTestCase.
    """
    from django.core import mail

    if request.config.pluginmanager.has_plugin("django"):
        blocker = request.getfixturevalue("django_db_blocker").unblock()
    else:
        blocker = None

    mail.outbox = []
    try:
        yield
    finally:
        if blocker is not None:
            blocker.__exit__(None, None, None)


def pytest_collection_modifyitems(config, items):
    """Asegura que los tests con @pytest.mark.django_db pidan el fixture db.

    Esto solo es necesario cuando pytest-django no está cargado (mutmut 3.x
    con `-p no:django`).
    """
    if config.pluginmanager.has_plugin("django"):
        return
    for item in items:
        if item.get_closest_marker("django_db") and "db" not in item.fixturenames:
            item.fixturenames.append("db")


@pytest.fixture(autouse=True)
def clear_cache():
    """Limpia el cache antes de cada test."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def client():
    """Cliente de test de Django (reemplaza el fixture de pytest-django)."""
    from django.test import Client
    return Client()


@pytest.fixture
def settings():
    """Emula el fixture ``settings`` de pytest-django.

    Permite ``settings.FOO = valor`` aplicando ``override_settings`` por cada
    asignación. Funciona igual con o sin pytest-django (necesario porque
    mutmut corre los tests con ``-p no:django``).
    """
    from django.test import override_settings

    class _Settings:
        def __init__(self):
            object.__setattr__(self, "_overrides", [])

        def __setattr__(self, name, value):
            ctx = override_settings(**{name: value})
            ctx.enable()
            self._overrides.append(ctx)

        def __delattr__(self, name):
            raise NotImplementedError("settings no soporta delattr")

    s = _Settings()
    try:
        yield s
    finally:
        for ctx in reversed(s._overrides):
            ctx.disable()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="user@test.com",
        username="user",
        password="testpass123",
    )


@pytest.fixture
def other_user(db):
    return User.objects.create_user(
        email="other@test.com",
        username="other",
        password="testpass123",
    )


@pytest.fixture
def authed_client(api_client, user):
    refresh = RefreshToken.for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return api_client


@pytest.fixture
def authed_client_other(other_user):
    """Cliente autenticado como other_user (instancia separada)."""
    client = APIClient()
    refresh = RefreshToken.for_user(other_user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return client


@pytest.fixture
def project(user):
    return Project.objects.create(owner=user, name="Proyecto Test")


@pytest.fixture
def tag(user):
    return Tag.objects.create(owner=user, name="Trabajo", color="#1976d2")


@pytest.fixture
def task(user, project):
    return Task.objects.create(
        owner=user,
        project=project,
        title="Tarea de test",
        state=Task.State.PENDING,
        priority=Task.Priority.P3_MEDIUM,
    )
