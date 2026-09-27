"""Autenticación por API key y throttles para la API pública."""
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication
from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle

from .models import APIKey

VALID_API_KEY_SCOPES = {"read", "write", "admin"}


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
    """Rate limiting para API keys: 1000/hour por key."""

    scope = "api_key"
    rate = "1000/hour"

    def get_cache_key(self, request, view):
        # Solo throttlear peticiones autenticadas con API key
        if not isinstance(getattr(request, "auth", None), APIKey):
            return None
        return f"throttle_apikey_{request.auth.pk}"


class APIKeyScopePermission(BasePermission):
    """Enforcement de scopes de API key a nivel global.

    - Auth por JWT/sesión → permitido (scope no aplica).
    - API key sin scope "read"/"write"/"admin" → denegado.
    - Métodos de lectura requieren "read" (o "write"/"admin").
    - Métodos de escritura requieren "write" o "admin".
    """

    def has_permission(self, request, view):
        api_key = getattr(request, "auth", None)
        if not isinstance(api_key, APIKey):
            return True
        scopes = set(api_key.scopes or []) & VALID_API_KEY_SCOPES
        if "admin" in scopes:
            return True
        if request.method in SAFE_METHODS:
            return bool(scopes & {"read", "write"})
        return "write" in scopes


class BurstRateThrottle(AnonRateThrottle):
    """Rate limiting burst: 60/min para anónimos."""
    scope = "burst"
    rate = "60/min"


class AuthenticatedRateThrottle(UserRateThrottle):
    """Rate limiting para usuarios autenticados: 300/hour."""
    scope = "authenticated"
    rate = "300/hour"


class LoginRateThrottle(AnonRateThrottle):
    """Rate limiting estricto para login: 10/min por IP."""
    scope = "login"
    rate = "10/min"


class RegisterRateThrottle(AnonRateThrottle):
    """Rate limiting para registro de cuentas: 5/hora por IP.

    Evita creación masiva de cuentas (spam, abuso de recursos).
    """
    scope = "register"
    rate = "5/hour"


class PasswordResetRateThrottle(AnonRateThrottle):
    """Rate limiting para solicitudes de reset de contraseña: 5/hora por IP.

    Evita abuso del envío de emails y enumeración por volumen.
    """
    scope = "password_reset"
    rate = "5/hour"


class IntakePublicRateThrottle(AnonRateThrottle):
    """Rate limiting para submissions públicas de formularios de intake:
    20/hora por IP (rate en DEFAULT_THROTTLE_RATES)."""
    scope = "intake_public"


class PublicShareRateThrottle(AnonRateThrottle):
    """Rate limiting para enlaces públicos de proyectos: 60/hora por IP."""
    scope = "public_share"


class InboundRateThrottle(AnonRateThrottle):
    """Rate limiting para canales de entrada (webhooks entrantes y
    email-to-task): 60/hora por IP. Scope compartido entre ambos
    endpoints — el bucket es el mismo."""
    scope = "inbound"


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
        if api_key and isinstance(api_key, APIKey) and not has_scope(api_key, "write"):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("API key sin permiso de escritura")
