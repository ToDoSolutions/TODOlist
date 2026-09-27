"""Views para automatizaciones."""
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import AutomationLog, AutomationRule, SlaPolicy
from .serializers import (
    AutomationLogSerializer,
    AutomationRuleSerializer,
    SlaPolicySerializer,
)


class AutomationRuleViewSet(viewsets.ModelViewSet):
    """CRUD de reglas de automatización."""
    serializer_class = AutomationRuleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return AutomationRule.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        # Cuota por usuario: evita abuso de recursos (cada regla evalúa en cada trigger)
        from django.conf import settings
        from rest_framework.exceptions import ValidationError

        max_rules = getattr(settings, "MAX_AUTOMATION_RULES_PER_USER", 100)
        if AutomationRule.objects.filter(owner=self.request.user).count() >= max_rules:
            raise ValidationError(
                {"detail": f"Límite de {max_rules} reglas de automatización alcanzado"}
            )
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=["post"])
    def test(self, request, pk=None):
        """Simula una regla con un contexto de prueba, sin ejecutar acciones.

        Solo evalúa las condiciones de ESTA regla contra una tarea real del
        usuario y reporta qué haría — nunca dispara otras reglas ni aplica
        efectos secundarios.
        """
        rule = self.get_object()
        from apps.tasks.models import Task

        from .engine import evaluate_conditions
        task = Task.objects.filter(owner=request.user).first()
        context = {"task": task, "user": request.user}
        conditions_met = evaluate_conditions(rule.conditions or [], context) if rule.conditions else True
        return Response({
            "rule": rule.name,
            "trigger": rule.trigger,
            "enabled": rule.enabled,
            "task_evaluated": task.id if task else None,
            "conditions_met": conditions_met,
            "would_execute": rule.enabled and conditions_met and task is not None,
            "action": rule.action,
            "action_params": rule.action_params,
        })

    @action(detail=True, methods=["get"])
    def logs(self, request, pk=None):
        """Historial de ejecuciones de una regla."""
        rule = self.get_object()
        logs = AutomationLog.objects.filter(rule=rule)[:50]
        serializer = AutomationLogSerializer(logs, many=True)
        return Response(serializer.data)


class SlaPolicyViewSet(viewsets.ModelViewSet):
    """CRUD de políticas SLA del usuario."""
    serializer_class = SlaPolicySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return SlaPolicy.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class AutomationLogViewSet(
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """Historial global de ejecuciones."""
    serializer_class = AutomationLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return AutomationLog.objects.filter(
            rule__owner=self.request.user
        ).select_related("rule")
