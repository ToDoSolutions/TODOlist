"""Autenticación Bearer para los endpoints SCIM 2.0.

El IdP (Entra ID / Okta / OneLogin) provisiona con un token estático
configurado vía ``SCIM_BEARER_TOKENS`` (separados por coma — permite
rotación sin corte). El usuario de la request queda como una identidad
de servicio: ``is_authenticated`` es True pero no es una cuenta real —
nunca debe usarse para acciones fuera del árbol ``/scim/v2/``.
"""
import hmac
import logging

from django.conf import settings
from django.utils.deprecation import MiddlewareMixin
from django.utils.functional import SimpleLazyObject

logger = logging.getLogger(__name__)


class _SCIMServiceIdentity:
    """Identidad sintética del provisionador SCIM (no es un User real)."""

    is_authenticated = True
    is_active = True
    is_staff = False
    pk = None
    email = "scim-provisioning@service"
    username = "scim-provisioning"

    def __str__(self):
        return "scim-service"


def _valid_scim_token(token: str) -> bool:
    tokens = getattr(settings, "SCIM_TOKENS", None) or []
    return any(hmac.compare_digest(token, t) for t in tokens if t)


def _resolve_user(request, original_user):
    """Si el Bearer es un token SCIM válido → identidad de servicio;
    si no, el usuario de sesión normal (un login válido también da
    acceso a SCIM — útil para explorar el endpoint desde la app)."""
    auth = request.META.get("HTTP_AUTHORIZATION", "")
    if auth.startswith("Bearer "):
        token = auth[7:].strip()
        if token and _valid_scim_token(token):
            return _SCIMServiceIdentity()
    # Fallback: request.user ya resuelto por auth normal (JWT/session).
    return original_user


class SCIMBearerAuthMiddleware(MiddlewareMixin):
    """Solo toca el árbol ``/scim/v2/``: traduce el Bearer del IdP a una
    identidad autenticada para que el middleware de django-scim admita
    la request. Fuera de SCIM no cambia nada (el token SCIM no sirve
    como credencial de la API normal)."""

    def process_request(self, request):
        if not getattr(settings, "SCIM_ENABLED", False):
            return
        if not request.path.startswith("/scim/v2"):
            return
        # Materializar el usuario ANTES de envolverlo: _resolve_user no
        # puede leer request.user (sería este mismo lazy → recursión).
        original_user = request.user
        request.user = SimpleLazyObject(
            lambda: _resolve_user(request, original_user)
        )
