from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone

from .services import register_device, apply_sync_operations, get_changes_since
from .models import SyncDevice, SyncOperation
from .serializers import SyncDeviceSerializer, SyncOperationSerializer


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def register_device_view(request):
    """Registra un dispositivo para sync offline."""
    device = register_device(
        user=request.user,
        device_id=request.data["device_id"],
        device_name=request.data.get("device_name", ""),
    )
    serializer = SyncDeviceSerializer(device)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def push_changes_view(request):
    """Recibe operaciones del cliente y las aplica."""
    operations = request.data.get("operations", [])
    results = apply_sync_operations(request.user, operations)
    return Response({"results": results})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def pull_changes_view(request):
    """Retorna cambios del servidor desde una fecha."""
    last_sync = request.query_params.get("since")
    if last_sync:
        from django.utils.dateparse import parse_datetime
        last_sync_dt = parse_datetime(last_sync)
        if last_sync_dt:
            changes = get_changes_since(request.user, last_sync_dt)
        else:
            changes = get_changes_since(request.user, timezone.now() - timezone.timedelta(days=30))
    else:
        changes = get_changes_since(request.user, timezone.now() - timezone.timedelta(days=30))

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
