"""Views para notificaciones."""
from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Notification, NotificationPreference
from .serializers import NotificationSerializer, NotificationPreferenceSerializer
from .services import mark_as_read, mark_all_as_read, get_unread_count


class NotificationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Gestión de notificaciones del usuario."""
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

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
        # Asegurar que existan preferencias para todos los tipos
        from .models import Notification
        for t in Notification.Type.values:
            NotificationPreference.objects.get_or_create(
                user=self.request.user,
                notification_type=t,
            )
        return NotificationPreference.objects.filter(user=self.request.user)
