"""Middleware WebSocket: autenticación JWT.

Métodos aceptados, en orden de preferencia:
1. Cookie httpOnly ``todolist_access`` (SPA — el navegador la envía
   automáticamente en el handshake; el token no es legible por JS).
2. Query param ``?token=`` (clientes no-browser, herramientas).

En ambos casos se valida la firma y expiración del JWT, y que el usuario
siga activo (is_active=True).
"""
from http.cookies import SimpleCookie
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser


@database_sync_to_async
def _user_from_token(token):
    from django.contrib.auth import get_user_model
    from rest_framework_simplejwt.tokens import AccessToken

    try:
        validated = AccessToken(token)
        user = get_user_model().objects.get(id=validated["user_id"])
        # Un usuario desactivado conserva tokens válidos hasta su expiración;
        # rechazar la conexión si la cuenta ya no está activa.
        return user if user.is_active else AnonymousUser()
    except Exception:  # noqa: BLE001  # boundary intencional: fallo externo no rompe el flujo
        return AnonymousUser()


def _token_from_cookie(scope):
    cookie_header = dict(scope.get("headers", [])).get(b"cookie", b"")
    if not cookie_header:
        return None
    cookies = SimpleCookie(cookie_header.decode())
    morsel = cookies.get("todolist_access")
    return morsel.value if morsel else None


class JwtAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        token = _token_from_cookie(scope)
        if not token:
            params = parse_qs(scope.get("query_string", b"").decode())
            token = params.get("token", [None])[0]
        # Sólo sobreescribe el usuario de sesión si hay token válido
        if token:
            scope["user"] = await _user_from_token(token)
        return await super().__call__(scope, receive, send)
