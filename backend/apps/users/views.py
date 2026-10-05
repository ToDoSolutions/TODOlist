import logging
import secrets

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    permission_classes,
    throttle_classes,
)
from rest_framework.generics import CreateAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .api_auth import (
    LoginRateThrottle,
    PasswordResetRateThrottle,
    RegisterRateThrottle,
)
from .cookie_auth import REFRESH_COOKIE, set_auth_cookies
from .security import is_2fa_locked, record_2fa_failure, reset_2fa_failures
from .serializers import RegisterSerializer, UserSerializer

User = get_user_model()


class TwoFactorTokenObtainPairSerializer(TokenObtainPairSerializer):
    """TokenObtainPair que exige código TOTP si el usuario tiene 2FA activo.

    El cliente envía {email, password, totp_code?}. Si el usuario tiene 2FA:
    - sin código → 400 con requires_2fa=true (el frontend repite el POST con código)
    - código inválido → 400 y contador de fallos (lockout tras N intentos)
    """

    def validate(self, attrs):
        request = self.context.get("request")
        user = authenticate(
            request=request,
            username=attrs[self.username_field],
            password=attrs["password"],
        )
        if user is None or not user.is_active:
            from rest_framework_simplejwt.exceptions import AuthenticationFailed
            raise AuthenticationFailed(
                self.error_messages["no_active_account"], "no_active_account"
            )

        # SSO enforcement por dominio: si la org reclamó el dominio del
        # email con sso_required, la contraseña no vale aunque sea
        # correcta — hay que entrar por el IdP (OIDC/SAML). Se chequea
        # tras autenticar para no revelar la política sin credenciales.
        domain = (user.email or "").split("@")[-1].lower()
        if domain:
            from apps.collaboration.models import Organization
            if Organization.objects.filter(
                sso_domain__iexact=domain, sso_required=True
            ).exists():
                from rest_framework import serializers
                raise serializers.ValidationError(
                    {
                        "email": (
                            "Tu organización exige inicio de sesión con "
                            "SSO. Usa el botón del proveedor."
                        ),
                        "sso_required": True,
                    }
                )

        tf = getattr(user, "twofactor", None)
        if tf and tf.is_enabled:
            if is_2fa_locked(user):
                from rest_framework import serializers
                raise serializers.ValidationError(
                    {"totp_code": "Demasiados intentos. Espera unos minutos."}
                )
            code = str(self.initial_data.get("totp_code", "")).strip()
            if not code:
                from rest_framework import serializers
                raise serializers.ValidationError(
                    {"totp_code": "Se requiere código 2FA", "requires_2fa": True}
                )
            if not (tf.verify_totp(code) or tf.use_backup_code(code)):
                record_2fa_failure(user)
                from rest_framework import serializers
                raise serializers.ValidationError({"totp_code": "Código 2FA inválido"})
            reset_2fa_failures(user)

        refresh = self.get_token(user)
        return {"refresh": str(refresh), "access": str(refresh.access_token)}


class LoginView(TokenObtainPairView):
    """Login con enforcement de 2FA y rate limit estricto (10/min por IP).

    Además del cuerpo JSON (tokens para clientes API), emite cookies httpOnly
    + cookie CSRF de doble envío para la SPA.
    """
    serializer_class = TwoFactorTokenObtainPairSerializer  # type: ignore[assignment]
    throttle_classes = [LoginRateThrottle]

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            set_auth_cookies(
                response,
                response.data["access"],
                response.data["refresh"],
                secrets.token_urlsafe(32),
            )
        return response


class CookieTokenRefreshView(TokenRefreshView):
    """Refresh que acepta el token por cookie httpOnly si no viene en el body
    y renueva las cookies al rotar."""

    def post(self, request, *args, **kwargs):
        if "refresh" not in request.data:
            refresh = request.COOKIES.get(REFRESH_COOKIE)
            if refresh:
                data = request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
                data["refresh"] = refresh
                request._full_data = data
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            set_auth_cookies(
                response,
                response.data["access"],
                response.data.get("refresh", ""),
                secrets.token_urlsafe(32),
            )
        return response


class RegisterView(CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    throttle_classes = [RegisterRateThrottle]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        out = UserSerializer(user, context=self.get_serializer_context())
        return Response(out.data, status=status.HTTP_201_CREATED)


class MeView(RetrieveUpdateAPIView):
    """Devuelve y permite actualizar el perfil del usuario autenticado."""

    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password(request):
    """Permite al usuario cambiar su contraseña proporcionando la actual."""
    current = request.data.get("current_password", "")
    new = request.data.get("new_password", "")

    if not current or not new:
        return Response(
            {"error": "Debes proporcionar current_password y new_password."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = request.user
    if not user.check_password(current):
        return Response(
            {"error": "La contraseña actual no es correcta."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        validate_password(new, user=user)
    except DjangoValidationError as e:
        return Response({"error": list(e.messages)}, status=status.HTTP_400_BAD_REQUEST)

    user.set_password(new)
    user.save()

    _revoke_all_tokens(user)
    return Response({"message": "Contraseña actualizada correctamente."})


def _revoke_all_tokens(user):
    """Blacklidea todos los refresh tokens del usuario (cierra sesiones)."""
    try:
        from rest_framework_simplejwt.token_blacklist.models import (
            BlacklistedToken,
            OutstandingToken,
        )
    except ImportError:
        # blacklist app no instalada — nada que revocar
        logging.getLogger(__name__).debug("revoke tokens: blacklist no disponible")
        return
    try:
        for token in OutstandingToken.objects.filter(user=user):
            BlacklistedToken.objects.get_or_create(token=token)
    except Exception:  # noqa: BLE001  # boundary intencional: no romper el flujo
        # Fallo real (BD, etc.): los refresh tokens antiguos siguen
        # válidos — visible en warning, no debug, para que el
        # operador pueda reaccionar.
        logging.getLogger(__name__).warning(
            "revoke tokens: fallo blacklisteando refresh tokens de user %s",
            user.pk,
            exc_info=True,
        )


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([PasswordResetRateThrottle])
def password_reset_request(request):
    """Solicita un enlace de reset de contraseña por email.

    Siempre devuelve 200 para no filtrar si el email existe (enumeración).
    El token usa PasswordResetTokenGenerator de Django: stateless,
    caduca con PASSWORD_RESET_TIMEOUT y queda invalidado tras el cambio.
    """
    from django.conf import settings
    from django.contrib.auth.tokens import default_token_generator
    from django.core.mail import send_mail
    from django.utils.encoding import force_bytes
    from django.utils.http import urlsafe_base64_encode

    email = (request.data.get("email") or "").strip().lower()
    if not email:
        return Response(
            {"error": "Indica tu email."}, status=status.HTTP_400_BAD_REQUEST
        )

    user = User.objects.filter(email__iexact=email, is_active=True).first()
    if user:
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        link = f"{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}"
        send_mail(
            "Restablecer contraseña - TODOlist",
            f"Para restablecer tu contraseña abre este enlace (válido 1 hora):\n\n{link}\n\n"
            "Si no lo has solicitado tú, ignora este mensaje.",
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )

    return Response(
        {"message": "Si el email existe, recibirás un enlace de restablecimiento."}
    )


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([PasswordResetRateThrottle])
def password_reset_confirm(request):
    """Confirma el reset: valida uid+token y establece la nueva contraseña.

    Revoca todas las sesiones del usuario para que solo la nueva
    contraseña quede activa.
    """
    from django.contrib.auth.tokens import default_token_generator
    from django.utils.encoding import force_str
    from django.utils.http import urlsafe_base64_decode

    uid = request.data.get("uid", "")
    token = request.data.get("token", "")
    new = request.data.get("new_password", "")

    if not uid or not token or not new:
        return Response(
            {"error": "Faltan uid, token o new_password."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if len(new) < 8:
        return Response(
            {"error": ["La contraseña debe tener al menos 8 caracteres."]},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(uid)))
    except (User.DoesNotExist, ValueError, TypeError, OverflowError):
        user = None

    if user is None or not default_token_generator.check_token(user, token):
        return Response(
            {"error": "El enlace no es válido o ha caducado."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        validate_password(new, user=user)
    except DjangoValidationError as e:
        return Response({"error": list(e.messages)}, status=status.HTTP_400_BAD_REQUEST)

    user.set_password(new)
    user.save()
    _revoke_all_tokens(user)
    return Response({"message": "Contraseña restablecida correctamente."})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([PasswordResetRateThrottle])
def send_verification_email(request):
    """Envía al usuario autenticado un enlace de verificación de email.

    Reutiliza el token stateless de Django (1h, un solo uso efectivo: la
    marca email_verified cambia el estado del usuario y invalida el token).
    """
    from django.conf import settings
    from django.contrib.auth.tokens import default_token_generator
    from django.core.mail import send_mail
    from django.utils.encoding import force_bytes
    from django.utils.http import urlsafe_base64_encode

    user = request.user
    if user.email_verified:
        return Response({"message": "El email ya está verificado."})

    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    link = f"{settings.FRONTEND_URL}/verify-email?uid={uid}&token={token}"
    send_mail(
        "Verifica tu email - TODOlist",
        f"Confirma tu dirección de email abriendo este enlace (válido 1 hora):\n\n{link}",
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )
    return Response({"message": "Email de verificación enviado."})


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([PasswordResetRateThrottle])
def verify_email(request):
    """Confirma el email con uid+token del enlace."""
    from django.contrib.auth.tokens import default_token_generator
    from django.utils import timezone
    from django.utils.encoding import force_str
    from django.utils.http import urlsafe_base64_decode

    uid = request.data.get("uid", "")
    token = request.data.get("token", "")
    if not uid or not token:
        return Response(
            {"error": "Faltan uid o token."}, status=status.HTTP_400_BAD_REQUEST
        )

    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(uid)))
    except (User.DoesNotExist, ValueError, TypeError, OverflowError):
        user = None

    if user is None or not default_token_generator.check_token(user, token):
        return Response(
            {"error": "El enlace no es válido o ha caducado."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user.email_verified = True
    user.email_verified_at = timezone.now()
    user.save(update_fields=["email_verified", "email_verified_at"])
    return Response({"message": "Email verificado correctamente."})
