from rest_framework import serializers

from .models import SyncDevice, SyncOperation


class SyncDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = SyncDevice
        fields = ["id", "device_id", "device_name", "last_sync_at", "is_active", "created_at"]
        read_only_fields = ["id", "last_sync_at", "is_active", "created_at"]


class SyncOperationSerializer(serializers.ModelSerializer):
    class Meta:
        model = SyncOperation
        fields = [
            "id", "device", "user", "op_type", "entity_type", "entity_id",
            "server_entity_id", "payload", "client_timestamp", "server_timestamp",
            "status", "conflict_status", "base_version", "conflict_data",
            "created_at", "applied_at",
        ]
        read_only_fields = ["id", "user", "server_entity_id", "server_timestamp", "status", "conflict_status", "conflict_data", "created_at", "applied_at"]
