"""Views para gestión de 2FA (TOTP)."""
import pyotp
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import TwoFactorSecret
from .security import is_2fa_locked, record_2fa_failure, reset_2fa_failures


def _check_2fa_rate_limit(user):
    """Devuelve Response de error si el usuario superó los intentos 2FA."""
    if is_2fa_locked(user):
        return Response(
            {"error": "Demasiados intentos. Espera unos minutos."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
    return None


@api_view(["GET", "POST", "DELETE"])
@permission_classes([IsAuthenticated])
def twofactor_manage(request):
    """Gestiona el 2FA del usuario.

    GET: estado actual
    POST: iniciar setup (genera secret y QR URI) o confirmar (verifica código)
    DELETE: desactivar 2FA
    """
    user = request.user

    if request.method == "GET":
        try:
            tf = user.twofactor
            return Response({
                "is_enabled": tf.is_enabled,
                "has_backup_codes": len(tf.backup_codes) > 0,
                "enabled_at": tf.enabled_at,
            })
        except TwoFactorSecret.DoesNotExist:
            return Response({"is_enabled": False, "has_backup_codes": False})

    if request.method == "POST":
        action = request.data.get("action", "setup")

        if action == "setup":
            # Generar nuevo secret
            secret = pyotp.random_base32()
            tf, created = TwoFactorSecret.objects.get_or_create(
                user=user, defaults={"secret": secret}
            )
            if not created:
                tf.secret = secret
                tf.is_enabled = False
                tf.save(update_fields=["secret", "is_enabled"])

            totp = pyotp.TOTP(secret)
            uri = totp.provisioning_uri(
                name=user.email, issuer_name="TODOlist"
            )
            return Response({
                "secret": secret,
                "otpauth_uri": uri,
                "message": "Escanea este QR con tu app autenticadora (Google Authenticator, Authy, etc.)",
            })

        elif action == "confirm":
            # Verificar código y activar
            limited = _check_2fa_rate_limit(user)
            if limited:
                return limited
            code = request.data.get("code", "")
            try:
                tf = user.twofactor
            except TwoFactorSecret.DoesNotExist:
                return Response(
                    {"error": "Primero inicia el setup"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if tf.verify_totp(code):
                reset_2fa_failures(user)
                tf.is_enabled = True
                from django.utils import timezone
                tf.enabled_at = timezone.now()
                tf.save(update_fields=["is_enabled", "enabled_at"])
                # Generar códigos de backup (se devuelven en claro solo aquí)
                backup_codes = tf.generate_backup_codes()
                return Response({
                    "message": "2FA activado correctamente",
                    "backup_codes": backup_codes,
                })
            record_2fa_failure(user)
            return Response(
                {"error": "Código inválido"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"error": "Acción inválida"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if request.method == "DELETE":
        limited = _check_2fa_rate_limit(user)
        if limited:
            return limited
        code = request.data.get("code", "")
        try:
            tf = user.twofactor
        except TwoFactorSecret.DoesNotExist:
            return Response(
                {"error": "2FA no está activado"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Verificar código TOTP o backup
        if tf.verify_totp(code) or tf.use_backup_code(code):
            reset_2fa_failures(user)
            tf.is_enabled = False
            tf.backup_codes = []
            tf.save(update_fields=["is_enabled", "backup_codes"])
            return Response({"message": "2FA desactivado"})
        record_2fa_failure(user)
        return Response(
            {"error": "Código inválido"},
            status=status.HTTP_400_BAD_REQUEST,
        )
