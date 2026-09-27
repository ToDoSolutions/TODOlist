from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ChatIntegrationViewSet, ChatMessageLogViewSet

router = DefaultRouter()
router.register(r"chat-integrations", ChatIntegrationViewSet, basename="chat-integration")
router.register(r"chat-logs", ChatMessageLogViewSet, basename="chat-log")

urlpatterns = [path("", include(router.urls))]
