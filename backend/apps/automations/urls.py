"""URLs para automatizaciones."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AutomationLogViewSet, AutomationRuleViewSet, SlaPolicyViewSet

router = DefaultRouter()
router.register(r"automation-rules", AutomationRuleViewSet, basename="automation-rule")
router.register(r"automation-logs", AutomationLogViewSet, basename="automation-log")
router.register(r"sla-policies", SlaPolicyViewSet, basename="sla-policy")

urlpatterns = [
    path("", include(router.urls)),
]
