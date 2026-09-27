from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from . import services
from .models import FeatureFlag
from .serializers import FeatureFlagSerializer


class FeatureFlagViewSet(viewsets.ModelViewSet):
    """CRUD de feature flags + acción `check` para evaluar estado."""

    serializer_class = FeatureFlagSerializer
    permission_classes = [IsAuthenticated]
    queryset = FeatureFlag.objects.all()
    lookup_field = "key"

    def get_permissions(self):
        # Solo staff puede crear/modificar/eliminar feature flags
        if self.action in ("create", "update", "partial_update", "destroy"):
            from rest_framework.permissions import IsAdminUser
            return [IsAdminUser()]
        return super().get_permissions()

    @action(detail=True, methods=["get"])
    def check(self, request, key=None):
        """GET /api/feature-flags/{key}/check/ -> {"enabled": bool}"""
        flag = self.get_object()
        enabled = services.is_enabled(flag.key, user=request.user)
        return Response({"enabled": enabled})
