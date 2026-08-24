"""Views para automatizaciones."""
from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import AutomationRule, AutomationLog
from .serializers import AutomationRuleSerializer, AutomationLogSerializer
from .engine import trigger_automation


class AutomationRuleViewSet(viewsets.ModelViewSet):
    """CRUD de reglas de automatización."""
    serializer_class = AutomationRuleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return AutomationRule.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=["post"])
    def test(self, request, pk=None):
        """Prueba una regla con un contexto simulado."""
        rule = self.get_object()
        from apps.tasks.models import Task
        task = Task.objects.filter(owner=request.user).first()
        context = {"task": task, "user": request.user}
        results = trigger_automation(rule.trigger, context)
        return Response({"results": results})

    @action(detail=True, methods=["get"])
    def logs(self, request, pk=None):
        """Historial de ejecuciones de una regla."""
        rule = self.get_object()
        logs = AutomationLog.objects.filter(rule=rule)[:50]
        serializer = AutomationLogSerializer(logs, many=True)
        return Response(serializer.data)


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
