"""Gating real de features: mapea prefijos de URL a flags.

Sin esto los FeatureFlag solo se podían crear y consultar — nada los
consumía. El middleware devuelve 404 (la feature "no existe" para ese
usuario) cuando el flag está off; el default cuando no hay fila en BD
viene de ``settings.FEATURE_FLAGS[key]`` (env ``FEATURE_*``).
"""
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

# prefijo de path (tras /api) -> key de flag
FLAGGED_PREFIXES = {
    "/api/ai/": "ai_assistant",
    "/api/sync/": "offline_sync",
    "/api/public-keys/": "e2e_encryption",
    "/api/encrypted-tasks/": "e2e_encryption",
}


def _resolve_flag_user(request):
    """Identidad para evaluar flags por usuario.

    ``request.user`` solo cubre sesión Django en middleware — los JWT
    los resuelve DRF dentro de la vista. Aquí resolvemos el token
    (Bearer header o cookie access) SIN enforcement CSRF: la vista
    sigue exigiéndolo; esto solo alimenta la evaluación del flag.
    """
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        return user

    raw = request.META.get("HTTP_AUTHORIZATION", "")
    cookie_token = request.COOKIES.get("todolist_access", "")
    try:
        from rest_framework_simplejwt.authentication import JWTAuthentication
        auth = JWTAuthentication()
        if raw.startswith("Bearer "):
            validated = auth.get_validated_token(raw[7:])
        elif cookie_token:
            validated = auth.get_validated_token(cookie_token)
        else:
            return user
        return auth.get_user(validated)
    except Exception:  # noqa: BLE001  # boundary: token inválido → anónimo
        return user


class FeatureFlagMiddleware(MiddlewareMixin):
    def process_request(self, request):
        for prefix, key in FLAGGED_PREFIXES.items():
            if request.path.startswith(prefix):
                from .services import is_enabled
                if not is_enabled(key, user=_resolve_flag_user(request)):
                    return JsonResponse(
                        {"detail": "Not found."}, status=404
                    )
                return None
        return None
