"""URLs para colaboración."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AuditLogViewSet,
    ExternalCalendarViewSet,
    InvitationViewSet,
    MeetingViewSet,
    MentionViewSet,
    OrganizationViewSet,
    ProjectMemberViewSet,
    TeamViewSet,
    WhiteboardViewSet,
    activity_feed,
)

router = DefaultRouter()
router.register(r"teams", TeamViewSet, basename="team")
router.register(r"project-members", ProjectMemberViewSet, basename="project-member")
router.register(r"invitations", InvitationViewSet, basename="invitation")
router.register(r"mentions", MentionViewSet, basename="mention")
router.register(r"audit-logs", AuditLogViewSet, basename="audit-log")
router.register(r"meetings", MeetingViewSet, basename="meeting")
router.register(r"organizations", OrganizationViewSet, basename="organization")
router.register(
    r"external-calendars", ExternalCalendarViewSet,
    basename="external-calendar",
)
router.register(r"whiteboards", WhiteboardViewSet, basename="whiteboard")

urlpatterns = [
    path("activity-feed/", activity_feed, name="activity_feed"),
    path("", include(router.urls)),
]
