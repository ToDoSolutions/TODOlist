"""Views para notificaciones."""
from django.conf import settings
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import CursorPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification, NotificationPreference, PushSubscription
from .serializers import NotificationPreferenceSerializer, NotificationSerializer
from .services import get_unread_count, mark_all_as_read, mark_as_read


class NotificationCursorPagination(CursorPagination):
    """Cursor sobre (created_at, id): estable ante inserciones concurrentes
    y eficiente en páginas profundas (sin OFFSET)."""
    ordering = ("-created_at", "-id")
    page_size = 50


class NotificationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Gestión de notificaciones del usuario."""
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = NotificationCursorPagination

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)

    @action(detail=False, methods=["get"])
    def unread_count(self, request):
        """Número de notificaciones no leídas."""
        return Response({"count": get_unread_count(request.user)})

    @action(detail=False, methods=["post"])
    def mark_all_read(self, request):
        """Marca todas como leídas."""
        count = mark_all_as_read(request.user)
        return Response({"marked": count})

    @action(detail=True, methods=["post"])
    def mark_read(self, request, pk=None):
        """Marca una notificación específica como leída."""
        notif = mark_as_read(pk, request.user)
        if not notif:
            return Response(
                {"error": "Notificación no encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(NotificationSerializer(notif).data)

    @action(detail=True, methods=["post"])
    def mark_unread(self, request, pk=None):
        """Marca una notificación como no leída."""
        try:
            notif = self.get_object()
        except Notification.DoesNotExist:
            return Response(
                {"error": "Notificación no encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )
        notif.read = False
        notif.read_at = None
        notif.save(update_fields=["read", "read_at"])
        return Response(NotificationSerializer(notif).data)


class NotificationPreferenceViewSet(
    mixins.ListModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Preferencias de notificación del usuario."""
    serializer_class = NotificationPreferenceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Auto-provisionar preferencias solo en list (una vez por usuario)
        if self.action == "list":
            from .models import Notification
            existing = set(
                NotificationPreference.objects.filter(
                    user=self.request.user
                ).values_list("notification_type", flat=True)
            )
            missing = [t for t in Notification.Type.values if t not in existing]
            if missing:
                NotificationPreference.objects.bulk_create(
                    [
                        NotificationPreference(
                            user=self.request.user, notification_type=t
                        )
                        for t in missing
                    ],
                    ignore_conflicts=True,
                )
        return NotificationPreference.objects.filter(user=self.request.user)


class VapidPublicKeyView(APIView):
    """Devuelve la clave pública VAPID para suscribirse a Web Push."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        public_key = getattr(settings, "VAPID_PUBLIC_KEY", "")
        if not public_key:
            return Response(
                {"detail": "Web Push no está configurado en el servidor"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({"publicKey": public_key})


class PushSubscriptionView(APIView):
    """Gestión de suscripciones Web Push del usuario autenticado.

    - GET: lista las suscripciones propias ({endpoint, created_at}).
    - POST: create-or-update por endpoint; si el endpoint existía para otro
      usuario (mismo navegador, otra sesión) se reasigna al actual.
    - DELETE: elimina una suscripción propia por endpoint.
    """
    permission_classes = [IsAuthenticated]

    @staticmethod
    def _serialize(sub):
        return {"endpoint": sub.endpoint, "created_at": sub.created_at}

    def get(self, request):
        subs = request.user.push_subscriptions.all()
        return Response([self._serialize(s) for s in subs])

    def post(self, request):
        endpoint = request.data.get("endpoint")
        keys = request.data.get("keys") or {}
        p256dh = keys.get("p256dh")
        auth = keys.get("auth")
        if not endpoint or not p256dh or not auth:
            return Response(
                {"detail": "endpoint, keys.p256dh y keys.auth son obligatorios"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        sub, created = PushSubscription.objects.update_or_create(
            endpoint=endpoint,
            defaults={
                "user": request.user,
                "p256dh": p256dh,
                "auth": auth,
            },
        )
        return Response(
            self._serialize(sub),
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def delete(self, request):
        endpoint = request.data.get("endpoint")
        if not endpoint:
            return Response(
                {"detail": "endpoint es obligatorio"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        deleted, _ = PushSubscription.objects.filter(
            user=request.user, endpoint=endpoint
        ).delete()
        if not deleted:
            return Response(
                {"detail": "Suscripción no encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)
