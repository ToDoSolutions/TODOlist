"""Tests del endpoint público de discovery de providers SSO.

GET /api/sso/providers/ refleja la config de SOCIALACCOUNT_PROVIDERS y
OIDC_ISSUER leída dinámicamente desde django.conf.settings — no hace falta
recargar INSTALLED_APPS ni el urlconf para simular OIDC habilitado.
"""
import pytest

pytestmark = pytest.mark.django_db


def _providers_by_id(data):
    return {p["id"]: p for p in data["providers"]}


class TestSsoProvidersEndpoint:
    """Contrato público de /api/sso/providers/ (AllowAny)."""

    def test_public_access(self, api_client):
        """El endpoint no requiere autenticación."""
        response = api_client.get("/api/sso/providers/")
        assert response.status_code == 200

    def test_lists_all_providers(self, api_client):
        """Devuelve github, google, oidc y saml con el contrato esperado."""
        response = api_client.get("/api/sso/providers/")
        assert response.status_code == 200
        providers = _providers_by_id(response.data)
        assert set(providers) == {"github", "google", "oidc", "saml"}
        for provider in providers.values():
            assert set(provider) == {"id", "name", "login_url", "enabled"}

    def test_login_urls(self, api_client):
        """Las login_url apuntan a los patrones reales de allauth."""
        providers = _providers_by_id(api_client.get("/api/sso/providers/").data)
        assert providers["github"]["login_url"] == "/api/auth/social/github/login/"
        assert providers["google"]["login_url"] == "/api/auth/social/google/login/"
        # openid_connect va bajo el prefijo "oidc" + provider_id
        assert providers["oidc"]["login_url"] == "/api/auth/social/oidc/oidc/login/"

    def test_oauth_providers_disabled_without_client_id(self, api_client, settings):
        """Sin client_id configurado, github/google salen disabled."""
        settings.SOCIALACCOUNT_PROVIDERS = {
            "github": {"APP": {"client_id": "", "secret": ""}},
            "google": {"APP": {"client_id": "", "secret": ""}},
        }
        providers = _providers_by_id(api_client.get("/api/sso/providers/").data)
        assert providers["github"]["enabled"] is False
        assert providers["google"]["enabled"] is False

    def test_oauth_providers_enabled_with_client_id(self, api_client, settings):
        """Con client_id configurado, github/google salen enabled."""
        settings.SOCIALACCOUNT_PROVIDERS = {
            "github": {"APP": {"client_id": "gh-client", "secret": "gh-secret"}},
            "google": {"APP": {"client_id": "g-client", "secret": "g-secret"}},
        }
        providers = _providers_by_id(api_client.get("/api/sso/providers/").data)
        assert providers["github"]["enabled"] is True
        assert providers["google"]["enabled"] is True

    def test_oidc_disabled_without_issuer(self, api_client, settings):
        """Con OIDC_ISSUER vacío, la entrada OIDC sale disabled."""
        settings.OIDC_ISSUER = ""
        providers = _providers_by_id(api_client.get("/api/sso/providers/").data)
        assert providers["oidc"]["enabled"] is False
        assert providers["oidc"]["name"] == "SSO"

    def test_oidc_enabled_with_issuer(self, api_client, settings):
        """Con OIDC_ISSUER definido, la entrada OIDC sale enabled."""
        settings.OIDC_ISSUER = "https://keycloak.example.com/realms/app"
        providers = _providers_by_id(api_client.get("/api/sso/providers/").data)
        assert providers["oidc"]["enabled"] is True
        assert providers["oidc"]["login_url"] == "/api/auth/social/oidc/oidc/login/"

    def test_oidc_custom_provider_id_and_name(self, api_client, settings):
        """OIDC_PROVIDER_ID/OIDC_DISPLAY_NAME personalizan la entrada OIDC."""
        settings.OIDC_ISSUER = "https://login.example.com/v2.0"
        settings.OIDC_PROVIDER_ID = "corp-sso"
        settings.OIDC_DISPLAY_NAME = "Corp SSO"
        providers = _providers_by_id(api_client.get("/api/sso/providers/").data)
        assert "corp-sso" in providers
        entry = providers["corp-sso"]
        assert entry["name"] == "Corp SSO"
        assert entry["enabled"] is True
        assert entry["login_url"] == "/api/auth/social/oidc/corp-sso/login/"
