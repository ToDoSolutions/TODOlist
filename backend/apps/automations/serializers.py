"""Serializers para automatizaciones."""
from rest_framework import serializers
from .models import AutomationRule, AutomationLog


class AutomationRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = AutomationRule
        fields = [
            "id", "name", "description", "enabled",
            "trigger", "conditions", "action", "action_params",
            "trigger_count", "last_triggered_at",
            "created_at", "updated_at",
        ]
        read_only_fields = ["trigger_count", "last_triggered_at", "created_at", "updated_at"]


class AutomationLogSerializer(serializers.ModelSerializer):
    rule_name = serializers.CharField(source="rule.name", read_only=True)

    class Meta:
        model = AutomationLog
        fields = [
            "id", "rule", "rule_name", "status",
            "trigger_data", "action_result", "error_message",
            "created_at",
        ]
        read_only_fields = fields
