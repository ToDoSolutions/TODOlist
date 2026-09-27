"""Routing de WebSocket consumers."""
from django.urls import path

from .consumers import NotificationConsumer, TaskConsumer

websocket_urlpatterns = [
    path("ws/tasks/", TaskConsumer.as_asgi()),
    path("ws/notifications/", NotificationConsumer.as_asgi()),
]
