from rest_framework import serializers

from apps.okrs.models import KeyResult, KeyResultUpdate, Objective


class KeyResultUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = KeyResultUpdate
        fields = [
            "id",
            "key_result",
            "user",
            "old_value",
            "new_value",
            "note",
            "created_at",
        ]
        read_only_fields = ["user", "old_value", "created_at"]


class KeyResultSerializer(serializers.ModelSerializer):
    updates = KeyResultUpdateSerializer(many=True, read_only=True)

    class Meta:
        model = KeyResult
        fields = [
            "id",
            "objective",
            "title",
            "target_value",
            "current_value",
            "unit",
            "owner",
            "due_date",
            "created_at",
            "updates",
        ]
        read_only_fields = ["owner", "current_value", "created_at"]


class ObjectiveSerializer(serializers.ModelSerializer):
    key_results = KeyResultSerializer(many=True, read_only=True)

    class Meta:
        model = Objective
        fields = [
            "id",
            "owner",
            "title",
            "description",
            "quarter",
            "year",
            "status",
            "progress",
            "created_at",
            "updated_at",
            "key_results",
        ]
        read_only_fields = ["owner", "progress", "created_at", "updated_at"]
