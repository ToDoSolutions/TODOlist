from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.okrs.views import (
    KeyResultUpdateViewSet,
    KeyResultViewSet,
    ObjectiveViewSet,
)

router = DefaultRouter()
router.register(r"objectives", ObjectiveViewSet, basename="objective")
router.register(r"key-results", KeyResultViewSet, basename="key-result")
router.register(r"kr-updates", KeyResultUpdateViewSet, basename="kr-update")

urlpatterns = [
    path("", include(router.urls)),
]
