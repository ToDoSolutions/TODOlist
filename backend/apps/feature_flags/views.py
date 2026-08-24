from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import FeatureFlag
from .serializers import FeatureFlagSerializer
from . import services


class FeatureFlagViewSet(viewsets.ModelViewSet):
    """CRUD de feature flags + acción `check` para evaluar estado."""

    serializer_class = FeatureFlagSerializer
    permission_classes = [IsAuthenticated]
    queryset = FeatureFlag.objects.all()
    lookup_field = "key"

    @action(detail=True, methods=["get"])
    def check(self, request, key=None):
        """GET /api/feature-flags/{key}/check/ -> {"enabled": bool}"""
        flag = self.get_object()
        enabled = services.is_enabled(flag.key, user=request.user)
        return Response({"enabled": enabled})
