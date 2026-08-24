"""Routing de WebSocket consumers."""
from django.urls import path
from .consumers import TaskConsumer, NotificationConsumer

websocket_urlpatterns = [
    path("ws/tasks/", TaskConsumer.as_asgi()),
    path("ws/notifications/", NotificationConsumer.as_asgi()),
]
