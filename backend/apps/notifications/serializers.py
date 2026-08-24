"""Serializers para notificaciones."""
from rest_framework import serializers
from .models import Notification, NotificationPreference


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id", "type", "title", "body", "task", "sprint",
            "action_url", "metadata", "read", "read_at",
            "sent_in_app", "sent_email", "created_at",
        ]
        read_only_fields = fields


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = [
            "id", "notification_type", "in_app_enabled",
            "email_enabled", "digest_enabled",
        ]
        read_only_fields = ["id", "notification_type"]
