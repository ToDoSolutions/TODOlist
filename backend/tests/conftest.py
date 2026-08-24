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
def clear_cache():
    """Limpia el cache antes de cada test."""
    cache.clear()
    yield
    cache.clear()


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
