from django.core.exceptions import PermissionDenied
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import SyncDevice, SyncOperation
from .serializers import SyncDeviceSerializer, SyncOperationSerializer
from .services import apply_sync_operations, get_changes_since, register_device


class SyncDeviceViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """ViewSet para gestión de dispositivos de sync offline.

    Permite listar, ver detalle, revocar (revoke) y eliminar (destroy)
    los dispositivos registrados del usuario.
    """

    serializer_class = SyncDeviceSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "device_id"

    def get_queryset(self):
        return SyncDevice.objects.filter(user=self.request.user)

    @action(detail=True, methods=["post"])
    def revoke(self, request, device_id=None):
        """Marca un dispositivo como inactivo (revocado)."""
        device = self.get_object()
        device.is_active = False
        device.save(update_fields=["is_active"])
        return Response(SyncDeviceSerializer(device).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"])
    def revoke_all(self, request):
        """Revoca TODOS los dispositivos del usuario (logout masivo).

        Equivale a "cerrar sesión en todos los dispositivos": cada uno
        tendrá que volver a registrarse para sincronizar.
        """
        qs = self.get_queryset().filter(is_active=True)
        count = qs.update(is_active=False)
        return Response({"revoked": count}, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def register_device_view(request):
    """Registra un dispositivo para sync offline."""
    device_id = request.data.get("device_id")
    if not device_id or not isinstance(device_id, str) or len(device_id) > 128:
        return Response(
            {"error": "device_id requerido (string, máx 128 chars)"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        device = register_device(
            user=request.user,
            device_id=device_id,
            device_name=request.data.get("device_name", "")[:200],
        )
    except PermissionDenied as e:
        return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
    serializer = SyncDeviceSerializer(device)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def push_changes_view(request):
    """Recibe operaciones del cliente y las aplica."""
    operations = request.data.get("operations", [])
    try:
        results = apply_sync_operations(request.user, operations)
    except PermissionDenied as e:
        return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    return Response({"results": results})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def pull_changes_view(request):
    """Retorna cambios del servidor desde una fecha."""
    last_sync = request.query_params.get("since")
    if last_sync:
        from django.utils.dateparse import parse_datetime
        last_sync_dt = parse_datetime(last_sync)
        if not last_sync_dt:
            return Response(
                {"error": "Formato de 'since' inválido (ISO 8601)"},
                status=status.HTTP_400_BAD_REQUEST,
            )
    else:
        last_sync_dt = timezone.now() - timezone.timedelta(days=30)
    changes = get_changes_since(request.user, last_sync_dt)

    # Actualizar last_sync_at del dispositivo
    device_id = request.query_params.get("device_id")
    if device_id:
        SyncDevice.objects.filter(device_id=device_id, user=request.user).update(
            last_sync_at=timezone.now()
        )

    return Response(changes)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_operations_view(request):
    """Lista el historial de operaciones de sync del usuario."""
    qs = SyncOperation.objects.filter(user=request.user).select_related("device").order_by("-created_at")[:100]
    serializer = SyncOperationSerializer(qs, many=True)
    return Response(serializer.data)
