from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DashboardViewSet, ShareLinkViewSet, public_share

router = DefaultRouter()
router.register(r"dashboards", DashboardViewSet, basename="dashboard")
router.register(r"share-links", ShareLinkViewSet, basename="share-link")

urlpatterns = [
    path("public/share/<str:token>/", public_share, name="public-share"),
    path("", include(router.urls)),
]
