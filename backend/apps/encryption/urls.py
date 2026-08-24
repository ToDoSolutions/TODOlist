from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import UserPublicKeyViewSet, EncryptedTaskViewSet

router = DefaultRouter()
router.register(r"public-keys", UserPublicKeyViewSet, basename="public-key")
router.register(r"encrypted-tasks", EncryptedTaskViewSet, basename="encrypted-task")

urlpatterns = [path("", include(router.urls))]
