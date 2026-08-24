"""Serializers para API keys."""
from rest_framework import serializers
from .models import APIKey


class APIKeySerializer(serializers.ModelSerializer):
    """Serializer para listar API keys (sin mostrar la key completa)."""
    class Meta:
        model = APIKey
        fields = [
            "id", "name", "key_prefix", "scopes",
            "is_active", "last_used_at", "expires_at", "created_at",
        ]
        read_only_fields = ["id", "key_prefix", "last_used_at", "created_at"]


class APIKeyCreateSerializer(serializers.Serializer):
    """Serializer para crear una API key. Retorna la key raw una sola vez."""
    name = serializers.CharField(max_length=120)
    scopes = serializers.ListField(
        child=serializers.CharField(), default=list, required=False
    )
    expires_at = serializers.DateTimeField(required=False, allow_null=True)
