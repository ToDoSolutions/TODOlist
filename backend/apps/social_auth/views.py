"""Views para social auth: retorna JWT tras login social."""
from django.http import JsonResponse, HttpResponseRedirect
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken


def social_jwt_callback(request):
    """Callback después de login social exitoso.
    Retorna tokens JWT para el frontend.
    """
    if not request.user.is_authenticated:
        return JsonResponse({"error": "No autenticado"}, status=401)

    refresh = RefreshToken.for_user(request.user)
    return JsonResponse({
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "user": {
            "id": request.user.id,
            "email": request.user.email,
            "username": request.user.username,
        },
    })
