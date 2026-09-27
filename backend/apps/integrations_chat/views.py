from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import ChatIntegration, ChatMessageLog
from .serializers import ChatIntegrationSerializer, ChatMessageLogSerializer
from .services import send_discord_message, send_slack_message


class ChatIntegrationViewSet(viewsets.ModelViewSet):
    serializer_class = ChatIntegrationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ChatIntegration.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=["post"])
    def test(self, request, pk=None):
        """Envía un mensaje de test a la integración."""
        integration = self.get_object()
        if integration.provider == "slack":
            success, code, err = send_slack_message(
                integration.webhook_url, "Test from TODOlist! ✅"
            )
        else:
            success, code, err = send_discord_message(
                integration.webhook_url, "Test from TODOlist! ✅"
            )
        return Response({"success": success, "status_code": code, "error": err})

    @action(detail=True, methods=["get"])
    def logs(self, request, pk=None):
        integration = self.get_object()
        logs = integration.message_logs.all()[:50]
        serializer = ChatMessageLogSerializer(logs, many=True)
        return Response(serializer.data)


class ChatMessageLogViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = ChatMessageLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ChatMessageLog.objects.filter(
            integration__owner=self.request.user
        ).select_related("integration")
