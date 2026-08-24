"""URLs para automatizaciones."""
from rest_framework.routers import DefaultRouter
from django.urls import path, include

from .views import AutomationRuleViewSet, AutomationLogViewSet

router = DefaultRouter()
router.register(r"automation-rules", AutomationRuleViewSet, basename="automation-rule")
router.register(r"automation-logs", AutomationLogViewSet, basename="automation-log")

urlpatterns = [
    path("", include(router.urls)),
]
