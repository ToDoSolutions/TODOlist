"""WebSocket consumers para real-time updates."""
from channels.generic.websocket import AsyncJsonWebsocketConsumer


class TaskConsumer(AsyncJsonWebsocketConsumer):
    """WebSocket para updates de tareas en tiempo real."""

    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        self.room_group = f"user_{user.id}_tasks"
        await self.channel_layer.group_add(self.room_group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, "room_group"):
            await self.channel_layer.group_discard(self.room_group, self.channel_name)

    async def task_updated(self, event):
        """Handler para notificaciones de tarea actualizada."""
        await self.send_json({
            "type": "task.updated",
            "task": event.get("task"),
        })

    async def task_created(self, event):
        """Handler para notificaciones de tarea creada."""
        await self.send_json({
            "type": "task.created",
            "task": event.get("task"),
        })

    async def task_deleted(self, event):
        """Handler para notificaciones de tarea eliminada."""
        await self.send_json({
            "type": "task.deleted",
            "task_id": event.get("task_id"),
        })

    async def notification_received(self, event):
        """Handler para notificaciones push."""
        await self.send_json({
            "type": "notification",
            "notification": event.get("notification"),
        })


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    """WebSocket para notificaciones en tiempo real."""

    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        self.room_group = f"user_{user.id}_notifications"
        await self.channel_layer.group_add(self.room_group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, "room_group"):
            await self.channel_layer.group_discard(self.room_group, self.channel_name)

    async def notification_new(self, event):
        """Handler para nueva notificación."""
        await self.send_json({
            "type": "notification.new",
            "notification": event.get("notification"),
        })

    async def notification_count(self, event):
        """Handler para contador de no leídas."""
        await self.send_json({
            "type": "notification.count",
            "count": event.get("count"),
        })
