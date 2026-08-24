from rest_framework import serializers
from .models import ChatIntegration, ChatMessageLog


class ChatIntegrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatIntegration
        fields = ["id", "owner", "provider", "webhook_url", "channel", "events", "is_active", "created_at"]
        read_only_fields = ["id", "owner", "created_at"]


class ChatMessageLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessageLog
        fields = ["id", "integration", "event", "payload", "status_code", "success", "error", "created_at"]
        read_only_fields = fields
