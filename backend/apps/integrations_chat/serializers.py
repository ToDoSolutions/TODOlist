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

    def validate_events(self, value):
        from apps.tasks.models import OutgoingWebhook
        valid = {c[0] for c in OutgoingWebhook.Event.choices}
        bad = [e for e in (value or []) if e not in valid]
        if bad:
            raise serializers.ValidationError(
                f"Eventos desconocidos: {', '.join(map(str, bad))}. "
                f"Válidos: {', '.join(sorted(valid))}."
            )
        return value


class ChatMessageLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessageLog
        fields = ["id", "integration", "event", "payload", "status_code", "success", "error", "created_at"]
        read_only_fields = fields
