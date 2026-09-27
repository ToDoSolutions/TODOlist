from rest_framework import serializers

from .models import ChatIntegration, ChatMessageLog


class ChatIntegrationSerializer(serializers.ModelSerializer):
    # El webhook_url contiene el secreto del webhook: write-only en la API
    webhook_url = serializers.CharField(write_only=True)

    class Meta:
        model = ChatIntegration
        fields = ["id", "owner", "provider", "webhook_url", "channel", "events", "is_active", "created_at"]
        read_only_fields = ["id", "owner", "created_at"]

    def validate_webhook_url(self, value):
        from .services import _is_safe_url
        if not _is_safe_url(value):
            raise serializers.ValidationError("URL de webhook no permitida.")
        return value


class ChatMessageLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessageLog
        fields = ["id", "integration", "event", "payload", "status_code", "success", "error", "created_at"]
        read_only_fields = fields
