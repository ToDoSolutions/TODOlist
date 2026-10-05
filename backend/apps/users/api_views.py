"""Views para gestión de API keys y cuenta de usuario."""
import logging
import re
from email.utils import parseaddr

from django.contrib.auth import get_user_model
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import (
    action,
    api_view,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .api_auth import InboundRateThrottle, SensitiveActionRateThrottle
from .api_serializers import APIKeyCreateSerializer, APIKeySerializer
from .models import APIKey

User = get_user_model()


class APIKeyViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Gestión de API keys del usuario."""
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return APIKey.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action == "create":
            return APIKeyCreateSerializer
        return APIKeySerializer

    def list(self, request, *args, **kwargs):
        from datetime import timedelta

        from django.utils import timezone

        queryset = self.get_queryset()
        serializer = APIKeySerializer(queryset, many=True)
        data = serializer.data
        # Aviso de rotación próxima: keys que expiran en <7 días
        warn = timezone.now() + timedelta(days=7)
        for item, key in zip(data, queryset):
            if key.expires_at and key.expires_at <= warn:
                item["rotation_warning"] = True
        return Response(data)

    def create(self, request, *args, **kwargs):
        serializer = APIKeyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        raw_key, hashed_key, prefix = APIKey.generate_key()
        api_key = APIKey.objects.create(
            user=request.user,
            name=serializer.validated_data["name"],
            key_prefix=prefix,
            hashed_key=hashed_key,
            scopes=serializer.validated_data.get("scopes", ["read"]),
            expires_at=serializer.validated_data.get("expires_at"),
        )

        return Response(
            {
                "id": api_key.id,
                "name": api_key.name,
                "key": raw_key,  # Solo se muestra una vez
                "key_prefix": prefix,
                "scopes": api_key.scopes,
                "message": "Guarda esta key en un lugar seguro. No se volverá a mostrar.",
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        """Revoca (desactiva) una API key."""
        api_key = self.get_object()
        api_key.is_active = False
        api_key.save(update_fields=["is_active"])
        return Response({"message": "API key revocada"})

    @action(detail=True, methods=["post"])
    def rotate(self, request, pk=None):
        """Rota una API key: emite una nueva con los mismos scopes y deja
        la antigua activa durante un grace period de 24h (después se desactiva).
        La nueva key solo se muestra una vez."""
        from datetime import timedelta

        from django.utils import timezone

        old = self.get_object()
        grace = timedelta(hours=24)
        raw_key, hashed_key, prefix = APIKey.generate_key()
        new = APIKey.objects.create(
            user=request.user,
            name=f"{old.name} (rotada)",
            key_prefix=prefix,
            hashed_key=hashed_key,
            scopes=old.scopes,
            expires_at=old.expires_at,
        )
        # Grace period: la vieja sigue funcionando 24h y luego expira
        old.expires_at = min(
            old.expires_at, timezone.now() + grace
        ) if old.expires_at else timezone.now() + grace
        old.save(update_fields=["expires_at"])
        return Response(
            {
                "id": new.id,
                "name": new.name,
                "key": raw_key,
                "key_prefix": prefix,
                "scopes": new.scopes,
                "grace_until": old.expires_at,
                "message": "Key rotada. La anterior expira en 24h.",
            },
            status=status.HTTP_201_CREATED,
        )


class UserMeView(viewsets.GenericViewSet):
    """Gestión de la propia cuenta de usuario."""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"])
    def me(self, request):
        """GET /api/users/me/ — info del usuario actual."""
        u = request.user
        return Response({
            "id": u.id,
            "email": u.email,
            "username": u.username,
            "is_active": u.is_active,
            "date_joined": u.date_joined,
            # El token es una credencial (crea tareas como el usuario):
            # solo se muestra en el POST que lo rota, nunca en lecturas.
            "has_inbound_email": bool(u.inbound_email_token),
            "weekly_capacity_hours": u.weekly_capacity_hours,
            "out_of_office": u.out_of_office,
            "out_of_office_until": (
                u.out_of_office_until.isoformat()
                if u.out_of_office_until else None
            ),
        })

    @action(detail=False, methods=["patch", "put"], url_path="update_profile")
    def update_profile(self, request):
        """PATCH/PUT /api/users/me/update_profile/ — actualiza el perfil.

        Usa UserSerializer (mismos campos editables que /api/auth/me/,
        incluido weekly_capacity_hours).
        """
        from .serializers import UserSerializer
        serializer = UserSerializer(
            request.user, data=request.data,
            partial=request.method == "PATCH",
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=False, methods=["post"], throttle_classes=[SensitiveActionRateThrottle])
    def deactivate(self, request):
        """POST /api/users/me/deactivate/ — desactiva la propia cuenta.
        Requiere la contraseña actual para confirmar."""
        password = request.data.get("password", "")
        user = request.user
        # Solo exigir password si el usuario tiene una utilizable
        # (cuentas OAuth-only pueden desactivarse sin ella)
        if user.has_usable_password() and (not password or not user.check_password(password)):
            return Response(
                {"error": "Contraseña requerida para desactivar la cuenta"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.is_active = False
        user.save(update_fields=["is_active"])
        return Response({"message": "Cuenta desactivada"})

    @action(detail=False, methods=["delete"], throttle_classes=[SensitiveActionRateThrottle])
    def delete_account(self, request):
        """DELETE /api/users/me/delete_account/ — elimina la propia cuenta.
        Requiere confirmación: ?confirm=true y la contraseña actual."""
        confirm = request.query_params.get("confirm", "false").lower() == "true"
        if not confirm:
            return Response(
                {"error": "Añade ?confirm=true para confirmar la eliminación"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = request.user
        password = request.data.get("password", "")
        if user.has_usable_password() and (not password or not user.check_password(password)):
            return Response(
                {"error": "Contraseña requerida para eliminar la cuenta"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.delete()
        return Response({"message": "Cuenta eliminada"}, status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["post"])
    def calendar_token(self, request):
        """POST /api/users/me/calendar_token/ — genera/rota el token del feed iCal.

        Cada llamada genera un token nuevo (el anterior queda revocado). El
        feed se suscribe como /api/tasks/calendar.ics/?token=<token> porque
        los clientes de calendario no envían JWT ni cookies.
        """
        import secrets
        user = request.user
        user.ical_token = secrets.token_urlsafe(32)
        user.save(update_fields=["ical_token"])
        return Response({
            "ical_token": user.ical_token,
            "feed_url": f"/api/tasks/calendar.ics/?token={user.ical_token}",
        })

    @action(detail=False, methods=["delete"])
    def calendar_token_revoke(self, request):
        """DELETE /api/users/me/calendar_token_revoke/ — revoca el token iCal."""
        user = request.user
        user.ical_token = None
        user.save(update_fields=["ical_token"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["post"])
    def email_token(self, request):
        """POST /api/users/me/email_token/ — genera/rota el token de
        email-to-task.

        Cada llamada genera un token nuevo (el anterior queda revocado). El
        provider de inbound email (SendGrid/Mailgun) envía a
        task-<token>@<dominio> y el payload POSTea a /api/inbound-email/.
        """
        import secrets
        user = request.user
        user.inbound_email_token = secrets.token_urlsafe(32)
        user.save(update_fields=["inbound_email_token"])
        return Response({
            "inbound_email_token": user.inbound_email_token,
            "inbound_address": f"task-{user.inbound_email_token}@inbound.todolist.local",
        })

    @action(detail=False, methods=["delete"])
    def email_token_revoke(self, request):
        """DELETE /api/users/me/email_token/ — revoca el token de
        email-to-task."""
        user = request.user
        user.inbound_email_token = None
        user.save(update_fields=["inbound_email_token"])
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_all_view(request):
    """POST /api/auth/logout-all/ — cierra sesión en TODOS los dispositivos.

    Blacklistea todos los outstanding refresh tokens del usuario y borra
    las cookies de la sesión actual. Los access tokens ya emitidos siguen
    siendo válidos hasta su expiración natural (≤60min).
    """
    from .cookie_auth import clear_auth_cookies

    count = 0
    try:
        from rest_framework_simplejwt.token_blacklist.models import (
            BlacklistedToken,
            OutstandingToken,
        )
        for token in OutstandingToken.objects.filter(user=request.user):
            _, created = BlacklistedToken.objects.get_or_create(token=token)
            count += int(created)
    except Exception:
        logging.getLogger(__name__).exception("logout_all: error blacklisteando tokens")

    response = Response({"message": "Sesiones cerradas en todos los dispositivos", "revoked": count})
    return clear_auth_cookies(response)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """POST /api/auth/logout/ — invalida el refresh token (blacklist)
    y borra las cookies httpOnly."""
    from .cookie_auth import REFRESH_COOKIE, clear_auth_cookies

    refresh = request.data.get("refresh") or request.COOKIES.get(REFRESH_COOKIE)
    if refresh:
        try:
            from rest_framework_simplejwt.tokens import RefreshToken
            RefreshToken(refresh).blacklist()
        except Exception:  # noqa: BLE001  # boundary intencional: fallo externo no rompe el flujo
            # token inválido o ya invalidado: logout idempotente
            logging.getLogger(__name__).debug("logout: refresh no blacklistable")
    response = Response({"message": "Sesión cerrada"})
    return clear_auth_cookies(response)


# --- Email-to-task (inbound email parse) ---

def _resolve_inbound_user(to_header):
    """Extrae el token del destinatario y resuelve el User.

    Acepta direcciones ``task-<token>@dominio`` o ``<token>@dominio``,
    posiblemente con nombre ("Nombre <task-x@d>") y múltiples
    destinatarios separados por comas. Devuelve el User o None.
    """
    for addr in (to_header or "").split(","):
        _, email_addr = parseaddr(addr)
        local = email_addr.split("@", 1)[0].strip()
        if not local:
            continue
        # El prefijo "task-" se detecta case-insensitive, pero el token se
        # compara exacto (urlsafe es case-sensitive por diseño)
        token = local[5:] if local.lower().startswith("task-") else local
        user = User.objects.filter(
            inbound_email_token=token, is_active=True
        ).first()
        if user is not None:
            return user
    return None


def _strip_quoted_reply(text):
    """Recorta la parte citada de una respuesta de email.

    Simple: corta en la primera línea que empieza por "On " o "El "
    (cabeceras de respuesta en inglés/español, p.ej. "On Mon, ... wrote:").
    """
    parts = re.split(r"\r?\n(?:On|El) ", text, maxsplit=1)
    return parts[0].strip()


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([InboundRateThrottle])
def inbound_email(request):
    """POST /api/inbound-email/ — convierte un email entrante en tarea.

    Payload provider-agnóstico (SendGrid/Mailgun inbound parse):
    {to, from, subject, text, html?}.

    - ``to`` contiene task-<token>@… → resuelve el usuario por su
      inbound_email_token (404 si no resuelve).
    - subject con ``[task-<id>]`` → crea un Comment en esa tarea, solo si
      ``from`` == user.email y el usuario tiene acceso de lectura a la
      tarea (el body se recorta quitando la parte citada).
    - resto → crea una Task (title=subject, description=text) en el
      primer proyecto del usuario.
    """
    to_header = request.data.get("to") or ""
    from_header = request.data.get("from") or ""
    subject = request.data.get("subject") or ""
    text = request.data.get("text") or ""

    user = _resolve_inbound_user(to_header)
    if user is None:
        return Response(
            {"error": "Destinatario desconocido"},
            status=status.HTTP_404_NOT_FOUND,
        )

    task_ref = re.search(r"\[task-(\d+)\]", subject, flags=re.IGNORECASE)
    if task_ref:
        sender = parseaddr(from_header)[1].strip().lower()
        if sender != user.email.lower():
            return Response(
                {"error": "El remitente no coincide con el propietario del token"},
                status=status.HTTP_403_FORBIDDEN,
            )
        from apps.tasks.models import Comment, Task
        # Paridad con REST (POST comments exige escritura en la tarea):
        # un viewer del proyecto no puede comentar ni vía email.
        task = Task.objects.for_user(user, write=True).filter(
            pk=int(task_ref.group(1))
        ).first()
        if task is None:
            return Response(
                {"error": "Tarea no encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )
        body = _strip_quoted_reply(text) or text.strip()
        comment = Comment.objects.create(
            task=task, author=user, body=body
        )
        return Response(
            {"created": "comment", "id": comment.id},
            status=status.HTTP_201_CREATED,
        )

    from apps.projects.models import Project
    from apps.tasks.models import Task
    project = Project.objects.filter(owner=user).first()
    from apps.tasks.services import next_position_seq
    pos, seq = next_position_seq(user, project)
    task = Task.objects.create(
        owner=user,
        project=project,
        title=(subject.strip() or "(sin asunto)")[:255],
        description=text,
        position=pos,
        seq=seq,
    )
    return Response(
        {"created": "task", "id": task.id},
        status=status.HTTP_201_CREATED,
    )
