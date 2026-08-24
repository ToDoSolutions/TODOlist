"""Autenticación por API key y throttles para la API pública."""
from rest_framework.authentication import BaseAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
from rest_framework import exceptions

from .models import APIKey


class APIKeyAuthentication(BaseAuthentication):
    """Autenticación mediante header Authorization: ApiKey <key>."""

    keyword = "ApiKey"

    def authenticate(self, request):
        auth = request.META.get("HTTP_AUTHORIZATION", "").split()
        if not auth or auth[0].lower() != self.keyword.lower():
            return None
        if len(auth) != 2:
            raise exceptions.AuthenticationFailed("Formato inválido. Use: ApiKey <key>")

        raw_key = auth[1]
        api_key_obj = APIKey.verify_key(raw_key)
        if not api_key_obj:
            raise exceptions.AuthenticationFailed("API key inválida o expirada")

        return (api_key_obj.user, api_key_obj)

    def authenticate_header(self, request):
        return self.keyword


class APIKeyRateThrottle(UserRateThrottle):
    """Rate limiting para API keys: 1000/hour por usuario."""
    scope = "api_key"
    rate = "1000/hour"


class BurstRateThrottle(AnonRateThrottle):
    """Rate limiting burst: 60/min para anónimos."""
    scope = "burst"
    rate = "60/min"


class AuthenticatedRateThrottle(UserRateThrottle):
    """Rate limiting para usuarios autenticados: 300/hour."""
    scope = "authenticated"
    rate = "300/hour"


def has_scope(api_key_obj, scope):
    """Verifica si una API key tiene un scope determinado."""
    if not api_key_obj:
        return True  # JWT auth, no API key
    scopes = api_key_obj.scopes or []
    if "admin" in scopes:
        return True
    return scope in scopes


class HasWriteScope:
    """Mixin para verificar scope de escritura en API keys."""
    def check_scope(self, request):
        # Si es API key auth, verificar scope
        api_key = getattr(request, "auth", None)
        if api_key and isinstance(api_key, APIKey):
            if not has_scope(api_key, "write"):
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("API key sin permiso de escritura")
