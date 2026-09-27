from rest_framework import serializers

from .models import Dashboard, ShareLink


class DashboardSerializer(serializers.ModelSerializer):
    shared_with = serializers.SerializerMethodField()
    is_owner = serializers.SerializerMethodField()

    class Meta:
        model = Dashboard
        fields = [
            "id", "name", "widgets", "is_default",
            "shared_with", "is_owner",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_shared_with(self, obj):
        return [
            {"id": u.id, "email": u.email}
            for u in obj.shared_with.all()
        ]

    def get_is_owner(self, obj):
        request = self.context.get("request")
        return bool(request and obj.owner_id == request.user.id)

    def validate_widgets(self, value):
        from .resolver import WIDGET_TYPES
        if not isinstance(value, list):
            raise serializers.ValidationError("widgets debe ser una lista")
        errors = []
        for i, w in enumerate(value):
            if not isinstance(w, dict) or "type" not in w:
                errors.append(f"widget {i}: 'type' requerido")
                continue
            if w["type"] not in WIDGET_TYPES:
                errors.append(
                    f"widget {i}: tipo desconocido '{w['type']}'. "
                    f"Disponibles: {sorted(WIDGET_TYPES)}"
                )
        if errors:
            raise serializers.ValidationError(errors)
        return value


class ShareLinkSerializer(serializers.ModelSerializer):
    """Enlace público a un proyecto (solo lectura para terceros)."""

    class Meta:
        model = ShareLink
        fields = ["id", "token", "project", "is_active", "created_at"]
        read_only_fields = ["id", "token", "is_active", "created_at"]
