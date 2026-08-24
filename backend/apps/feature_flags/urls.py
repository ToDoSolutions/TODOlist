from rest_framework.routers import DefaultRouter

from .views import FeatureFlagViewSet

router = DefaultRouter()
router.register(r"feature-flags", FeatureFlagViewSet, basename="feature-flag")

urlpatterns = router.urls
