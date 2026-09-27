from django.urls import path

from .health import liveness, readiness
from .metrics import metrics_view

urlpatterns = [
    path("metrics/", metrics_view, name="prometheus-metrics"),
    path("health/", liveness, name="health-live"),
    path("health/ready/", readiness, name="health-ready"),
]
