"""Autenticación JWT por cookie httpOnly con protección CSRF double-submit.

Las cookies httpOnly no son legibles por JavaScript, mitigando el robo de
tokens vía XSS. Como contrapartida, las cookies se envían automáticamente,
por lo que los métodos no seguros requieren el header ``X-CSRFToken``
coincidiendo con la cookie legible ``todolist_csrf`` (patrón double-submit).

El header ``Authorization: Bearer`` sigue funcionando (clientes no-browser,
API keys, tests); la cookie solo es un mecanismo adicional.
"""
from datetime import timedelta
from typing import cast

from django.conf import settings
from rest_framework import exceptions
from rest_framework.permissions import SAFE_METHODS
from rest_framework_simplejwt.authentication import JWTAuthentication

ACCESS_COOKIE = "todolist_access"
REFRESH_COOKIE = "todolist_refresh"
CSRF_COOKIE = "todolist_csrf"
CSRF_HEADER = "HTTP_X_CSRFTOKEN"


class CookieJWTAuthentication(JWTAuthentication):
    """JWT via cookie httpOnly; exige double-submit CSRF en métodos no seguros."""

    def authenticate(self, request):
        raw = request.COOKIES.get(ACCESS_COOKIE)
        if not raw:
            return None  # No hay cookie: que lo intente el header Bearer
        self._enforce_csrf(request)
        validated = self.get_validated_token(raw)
        return self.get_user(validated), validated

    def _enforce_csrf(self, request):
        if request.method in SAFE_METHODS:
            return
        cookie_token = request.COOKIES.get(CSRF_COOKIE, "")
        header_token = request.META.get(CSRF_HEADER, "")
        if not cookie_token or not header_token or cookie_token != header_token:
            raise exceptions.PermissionDenied("CSRF token inválido o ausente")


def set_auth_cookies(response, access: str, refresh: str, csrf: str):
    """Establece las cookies de autenticación en una respuesta."""
    secure = getattr(settings, "AUTH_COOKIE_SECURE", not settings.DEBUG)
    common = {"secure": secure, "samesite": "Lax", "path": "/"}
    access_ttl = cast(timedelta, settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"])
    refresh_ttl = cast(timedelta, settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"])
    response.set_cookie(
        ACCESS_COOKIE, access, httponly=True,
        max_age=int(access_ttl.total_seconds()),
        **common,
    )
    response.set_cookie(
        REFRESH_COOKIE, refresh, httponly=True,
        max_age=int(refresh_ttl.total_seconds()),
        **common,
    )
    # Cookie legible por JS: double-submit token (no es secreto de sesión)
    response.set_cookie(CSRF_COOKIE, csrf, httponly=False, **common)
    return response


def clear_auth_cookies(response):
    for name in (ACCESS_COOKIE, REFRESH_COOKIE, CSRF_COOKIE):
        response.delete_cookie(name, path="/")
    return response
