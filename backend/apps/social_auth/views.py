"""Views para social auth: retorna JWT tras login social."""
from django.conf import settings
from django.http import JsonResponse
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken


def _oauth_app_client_id(providers_cfg, provider_id):
    """Devuelve el client_id configurado para un provider OAuth2 (APP singular)."""
    app = (providers_cfg.get(provider_id) or {}).get("APP") or {}
    return app.get("client_id", "")


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def sso_providers(request):
    """Lista pública de providers SSO y si están configurados.

    El frontend consume ``login_url`` directamente (href); ``enabled`` indica
    si el provider tiene credenciales configuradas en el backend.
    """
    providers_cfg = getattr(settings, "SOCIALACCOUNT_PROVIDERS", {})

    # OIDC: provider con nombre; la URL incluye el prefijo "oidc"
    # (SOCIALACCOUNT_OPENID_CONNECT_URL_PREFIX) + el provider_id.
    oidc_issuer = getattr(settings, "OIDC_ISSUER", "")
    oidc_id = getattr(settings, "OIDC_PROVIDER_ID", "oidc")
    oidc_name = getattr(settings, "OIDC_DISPLAY_NAME", "SSO")
    oidc_prefix = getattr(settings, "SOCIALACCOUNT_OPENID_CONNECT_URL_PREFIX", "oidc")

    return Response(
        {
            "providers": [
                {
                    "id": "github",
                    "name": "GitHub",
                    "login_url": "/api/auth/social/github/login/",
                    "enabled": bool(_oauth_app_client_id(providers_cfg, "github")),
                },
                {
                    "id": "google",
                    "name": "Google",
                    "login_url": "/api/auth/social/google/login/",
                    "enabled": bool(_oauth_app_client_id(providers_cfg, "google")),
                },
                {
                    "id": oidc_id,
                    "name": oidc_name,
                    "login_url": f"/api/auth/social/{oidc_prefix}/{oidc_id}/login/",
                    "enabled": bool(oidc_issuer),
                },
                {
                    "id": getattr(settings, "SAML_PROVIDER_ID", "saml"),
                    "name": getattr(settings, "SAML_DISPLAY_NAME", "SAML SSO"),
                    "login_url": (
                        f"/api/auth/social/saml/"
                        f"{getattr(settings, 'SAML_PROVIDER_ID', 'saml')}/login/"
                    ),
                    "enabled": bool(getattr(settings, "SAML_IDP_SSO_URL", "")),
                },
            ]
        }
    )


def social_jwt_callback(request):
    """Callback después de login social exitoso.
    Retorna tokens JWT para el frontend.
    Si el usuario tiene 2FA activo, el social login no lo bypasea:
    se exige login por contraseña + TOTP.
    """
    if not request.user.is_authenticated:
        return JsonResponse({"error": "No autenticado"}, status=401)

    tf = getattr(request.user, "twofactor", None)
    if tf and tf.is_enabled:
        return JsonResponse(
            {"error": "La cuenta requiere 2FA. Inicia sesión con email y contraseña."},
            status=401,
        )

    import secrets

    from apps.users.cookie_auth import set_auth_cookies

    refresh = RefreshToken.for_user(request.user)
    # Cuando el navegador aterriza aquí tras un flujo allauth (OIDC/Google),
    # ?next= indica a dónde volver (la app). Sin next, se responde JSON para
    # clientes API que consuman los tokens directamente.
    next_url = request.GET.get("next")
    if next_url:
        from django.http import HttpResponseRedirect
        from django.utils.http import url_has_allowed_host_and_scheme

        if url_has_allowed_host_and_scheme(next_url, allowed_hosts=set()):
            response = HttpResponseRedirect(next_url)
        else:
            response = JsonResponse({"error": "next no permitido"}, status=400)
            return response
    else:
        response = JsonResponse({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": {
                "id": request.user.id,
                "email": request.user.email,
                "username": request.user.username,
            },
        })
    return set_auth_cookies(
        response, str(refresh.access_token), str(refresh), secrets.token_urlsafe(32)
    )
