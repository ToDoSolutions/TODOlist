from django.urls import path
from .views import register_device_view, push_changes_view, pull_changes_view, list_operations_view

urlpatterns = [
    path("sync/register-device/", register_device_view, name="sync-register-device"),
    path("sync/push/", push_changes_view, name="sync-push"),
    path("sync/pull/", pull_changes_view, name="sync-pull"),
    path("sync/operations/", list_operations_view, name="sync-operations"),
]
