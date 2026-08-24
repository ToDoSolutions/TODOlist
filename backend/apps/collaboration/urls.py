"""URLs para colaboración."""
from rest_framework.routers import DefaultRouter
from django.urls import path, include

from .views import (
    TeamViewSet, ProjectMemberViewSet, InvitationViewSet,
    MentionViewSet, AuditLogViewSet,
)

router = DefaultRouter()
router.register(r"teams", TeamViewSet, basename="team")
router.register(r"project-members", ProjectMemberViewSet, basename="project-member")
router.register(r"invitations", InvitationViewSet, basename="invitation")
router.register(r"mentions", MentionViewSet, basename="mention")
router.register(r"audit-logs", AuditLogViewSet, basename="audit-log")

urlpatterns = [
    path("", include(router.urls)),
]
