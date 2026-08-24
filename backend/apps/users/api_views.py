"""Views para gestión de API keys."""
from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import APIKey
from .api_serializers import APIKeySerializer, APIKeyCreateSerializer


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
        queryset = self.get_queryset()
        serializer = APIKeySerializer(queryset, many=True)
        return Response(serializer.data)

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
