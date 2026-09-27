from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import EncryptedTaskViewSet, UserPublicKeyViewSet

router = DefaultRouter()
router.register(r"public-keys", UserPublicKeyViewSet, basename="public-key")
router.register(r"encrypted-tasks", EncryptedTaskViewSet, basename="encrypted-task")

urlpatterns = [path("", include(router.urls))]
