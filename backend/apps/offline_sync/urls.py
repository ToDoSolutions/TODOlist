from django.urls import path

from .views import (
    SyncDeviceViewSet,
    list_operations_view,
    pull_changes_view,
    push_changes_view,
    register_device_view,
)

urlpatterns = [
    path("sync/register-device/", register_device_view, name="sync-register-device"),
    path("sync/push/", push_changes_view, name="sync-push"),
    path("sync/pull/", pull_changes_view, name="sync-pull"),
    path("sync/operations/", list_operations_view, name="sync-operations"),
    path("sync/devices/", SyncDeviceViewSet.as_view({"get": "list"}), name="sync-devices-list"),
    path("sync/devices/revoke_all/", SyncDeviceViewSet.as_view({"post": "revoke_all"}), name="sync-devices-revoke-all"),
    path("sync/devices/<str:device_id>/", SyncDeviceViewSet.as_view({"get": "retrieve", "delete": "destroy"}), name="sync-devices-detail"),
    path("sync/devices/<str:device_id>/revoke/", SyncDeviceViewSet.as_view({"post": "revoke"}), name="sync-devices-revoke"),
]
