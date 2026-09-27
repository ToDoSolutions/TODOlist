"""Serializers para automatizaciones."""
from rest_framework import serializers

from .models import AutomationLog, AutomationRule


class AutomationRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = AutomationRule
        fields = [
            "id", "name", "description", "enabled",
            "trigger", "conditions", "action", "action_params",
            "schedule_hours",
            "trigger_count", "last_triggered_at",
            "created_at", "updated_at",
        ]
        read_only_fields = ["trigger_count", "last_triggered_at", "created_at", "updated_at"]

    def validate_conditions(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("conditions debe ser una lista")
        for cond in value:
            if not isinstance(cond, dict) or "field" not in cond or "operator" not in cond:
                raise serializers.ValidationError(
                    "Cada condición debe ser {field, operator, value}"
                )
            if cond["operator"] not in [c[0] for c in AutomationRule.ConditionOperator.choices]:
                raise serializers.ValidationError(
                    f"Operador inválido: {cond['operator']}"
                )
        return value

    def validate(self, data):
        # Solo validar params cuando se cambia la acción o los params explícitamente
        if "action" not in data and "action_params" not in data:
            return data
        action = data.get("action", getattr(self.instance, "action", None))
        params = data.get("action_params", getattr(self.instance, "action_params", {})) or {}
        if not isinstance(params, dict):
            raise serializers.ValidationError({"action_params": "debe ser un objeto"})

        from apps.tasks.models import Task
        if action == AutomationRule.Action.SET_STATE:
            if params.get("state") not in [c[0] for c in Task.State.choices]:
                raise serializers.ValidationError(
                    {"action_params": "state inválido o ausente"}
                )
        elif action == AutomationRule.Action.SET_PRIORITY:
            if params.get("priority") not in [c[0] for c in Task.Priority.choices]:
                raise serializers.ValidationError(
                    {"action_params": "priority inválida o ausente"}
                )
        elif action == AutomationRule.Action.SET_DUE_DATE:
            days = params.get("days")
            date_val = params.get("date")
            if days is None and not date_val:
                raise serializers.ValidationError(
                    {"action_params": "set_due_date requiere 'days' o 'date'"}
                )
            if days is not None and not isinstance(days, int):
                raise serializers.ValidationError(
                    {"action_params": "'days' debe ser entero"}
                )
        elif action == AutomationRule.Action.MOVE_TO_SPRINT and not params.get("sprint_id"):
            raise serializers.ValidationError(
                {"action_params": "sprint_id requerido"}
            )
        return data


class SlaPolicySerializer(serializers.ModelSerializer):
    class Meta:
        from .models import SlaPolicy
        model = SlaPolicy
        fields = [
            "id", "name", "priority", "response_hours", "resolution_hours",
            "bump_priority", "notify_owner", "notify_assignee", "enabled",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, data):
        # unique(owner, priority): validado aquí porque owner no va en el payload
        request = self.context.get("request")
        priority = data.get(
            "priority", getattr(self.instance, "priority", None)
        )
        if request and priority is not None:
            from .models import SlaPolicy
            qs = SlaPolicy.objects.filter(owner=request.user, priority=priority)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"priority": "Ya existe una política para esa prioridad."}
                )
        resolution = data.get(
            "resolution_hours",
            getattr(self.instance, "resolution_hours", None),
        )
        response = data.get(
            "response_hours",
            getattr(self.instance, "response_hours", None),
        )
        if resolution is not None and response is not None and response > resolution:
            raise serializers.ValidationError(
                {"response_hours": "no puede superar resolution_hours"}
            )
        return data


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
