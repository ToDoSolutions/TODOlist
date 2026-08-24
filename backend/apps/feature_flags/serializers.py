from rest_framework import serializers

from .models import FeatureFlag


class FeatureFlagSerializer(serializers.ModelSerializer):
    """Serializer para FeatureFlag.

    `enabled_users` se expone como una lista de IDs de usuario; DRF
    resuelve automáticamente el queryset del modelo relacionado.
    """

    class Meta:
        model = FeatureFlag
        fields = [
            "id", "key", "name", "description",
            "is_enabled", "enabled_users",
            "enabled_percentage", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
