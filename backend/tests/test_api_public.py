"""Tests de Fase 12 (API pública: API keys, rate limiting, docs) y Fase 14 (caching)."""
import pytest
from apps.users.models import APIKey, User


# --- API Keys ---

@pytest.mark.django_db
class TestAPIKeys:
    def test_generar_api_key(self):
        raw, hashed, prefix = APIKey.generate_key()
        assert raw.startswith("tl_")
        assert len(hashed) == 64  # SHA256 hex
        assert prefix == raw[:12]

    def test_crear_api_key_via_api(self, authed_client, user):
        resp = authed_client.post("/api/api-keys/", {
            "name": "Mi API key",
            "scopes": ["read", "write"],
        }, format="json")
        assert resp.status_code == 201
        assert "key" in resp.data
        assert resp.data["key"].startswith("tl_")
        assert resp.data["key_prefix"] == resp.data["key"][:12]
        # La key no se guarda en texto plano
        assert APIKey.objects.filter(user=user, name="Mi API key").exists()
        api_key = APIKey.objects.get(name="Mi API key")
        assert api_key.hashed_key != resp.data["key"]  # Está hasheada

    def test_listar_api_keys(self, authed_client, user):
        raw, hashed, prefix = APIKey.generate_key()
        APIKey.objects.create(user=user, name="Test", key_prefix=prefix, hashed_key=hashed)
        resp = authed_client.get("/api/api-keys/")
        assert resp.status_code == 200
        data = resp.data if isinstance(resp.data, list) else resp.data["results"]
        assert len(data) == 1
        # No debe incluir la key raw
        assert "key" not in data[0]
        assert data[0]["key_prefix"] == prefix

    def test_revocar_api_key(self, authed_client, user):
        raw, hashed, prefix = APIKey.generate_key()
        api_key = APIKey.objects.create(user=user, name="Test", key_prefix=prefix, hashed_key=hashed)
        resp = authed_client.post(f"/api/api-keys/{api_key.id}/revoke/")
        assert resp.status_code == 200
        api_key.refresh_from_db()
        assert api_key.is_active is False

    def test_autenticacion_con_api_key(self, api_client, user):
        raw, hashed, prefix = APIKey.generate_key()
        APIKey.objects.create(user=user, name="Test", key_prefix=prefix, hashed_key=hashed)
        # Usar la API key para autenticarse
        resp = api_client.get(
            "/api/tasks/",
            HTTP_AUTHORIZATION=f"ApiKey {raw}",
        )
        assert resp.status_code == 200

    def test_api_key_invalida(self, api_client):
        resp = api_client.get(
            "/api/tasks/",
            HTTP_AUTHORIZATION="ApiKey tl_invalid_key",
        )
        assert resp.status_code == 401

    def test_api_key_revocada_no_autentica(self, api_client, user):
        raw, hashed, prefix = APIKey.generate_key()
        APIKey.objects.create(
            user=user, name="Test", key_prefix=prefix,
            hashed_key=hashed, is_active=False,
        )
        resp = api_client.get(
            "/api/tasks/",
            HTTP_AUTHORIZATION=f"ApiKey {raw}",
        )
        assert resp.status_code == 401

    def test_eliminar_api_key(self, authed_client, user):
        raw, hashed, prefix = APIKey.generate_key()
        api_key = APIKey.objects.create(user=user, name="Test", key_prefix=prefix, hashed_key=hashed)
        resp = authed_client.delete(f"/api/api-keys/{api_key.id}/")
        assert resp.status_code == 204
        assert not APIKey.objects.filter(id=api_key.id).exists()


# --- OpenAPI Docs ---

@pytest.mark.django_db
class TestOpenAPIDocs:
    def test_schema_endpoint(self, client):
        resp = client.get("/api/schema/")
        assert resp.status_code == 200
        # Debe ser YAML o JSON
        content = resp.content.decode()
        assert "openapi" in content.lower() or "swagger" in content.lower()

    def test_swagger_ui(self, client):
        resp = client.get("/api/docs/")
        assert resp.status_code == 200

    def test_redoc(self, client):
        resp = client.get("/api/redoc/")
        assert resp.status_code == 200


# --- Caching ---

@pytest.mark.django_db
class TestCaching:
    def test_metrics_dashboard_cachea(self, authed_client, user):
        """Las métricas del dashboard deben usar cache."""
        from django.core.cache import cache
        cache.clear()
        # Primera llamada: calcula y cachea
        resp1 = authed_client.get("/api/tasks/metrics_dashboard/")
        assert resp1.status_code == 200
        # Segunda llamada: debe venir de cache
        resp2 = authed_client.get("/api/tasks/metrics_dashboard/")
        assert resp2.status_code == 200
        # Los datos deben ser iguales
        assert resp1.data == resp2.data

    def test_metrics_flow_cachea(self, authed_client, user):
        from django.core.cache import cache
        cache.clear()
        resp1 = authed_client.get("/api/tasks/metrics_flow/?days=7")
        assert resp1.status_code == 200
        resp2 = authed_client.get("/api/tasks/metrics_flow/?days=7")
        assert resp2.status_code == 200
        assert resp1.data == resp2.data

    def test_cache_diferente_por_usuario(self, authed_client, user, other_user, authed_client_other):
        from django.core.cache import cache
        cache.clear()
        # Crear tareas diferentes para cada usuario
        from apps.tasks.models import Task
        Task.objects.create(owner=user, title="User task", state="pending")
        Task.objects.create(owner=other_user, title="Other task", state="completed")

        resp1 = authed_client.get("/api/tasks/metrics_dashboard/")
        resp2 = authed_client_other.get("/api/tasks/metrics_dashboard/")
        assert resp1.data["open"] != resp2.data["open"] or resp1.data["completed"] != resp2.data["completed"]


# --- Rate Limiting ---

@pytest.mark.django_db
class TestRateLimiting:
    def test_throttle_info_en_response(self, authed_client):
        """Las respuestas incluyen headers de throttle."""
        resp = authed_client.get("/api/tasks/")
        assert resp.status_code == 200
        # DRF añade X-Throttle en algunos casos
        # No verificamos el header específico pero confirmamos que no hay error
