from rest_framework import serializers

from .models import AiSuggestion


class AiSuggestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AiSuggestion
        fields = [
            "id",
            "user",
            "task",
            "suggestion_type",
            "input_data",
            "output_data",
            "confidence",
            "created_at",
        ]
        read_only_fields = ["id", "user", "created_at"]
