from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    IntakeFormViewSet,
    IntakeSubmissionViewSet,
    public_intake_schema,
    public_intake_submit,
)

router = DefaultRouter()
router.register(r"intake-forms", IntakeFormViewSet, basename="intake-form")
router.register(
    r"intake-submissions", IntakeSubmissionViewSet, basename="intake-submission"
)

urlpatterns = [
    path(
        "intake-forms/public/<str:token>/",
        public_intake_schema,
        name="intake-public-schema",
    ),
    path(
        "intake-forms/public/<str:token>/submit/",
        public_intake_submit,
        name="intake-public-submit",
    ),
    path("", include(router.urls)),
]
