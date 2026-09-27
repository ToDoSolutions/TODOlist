from rest_framework.routers import DefaultRouter

from .views import (
    PortfolioViewSet,
    ProjectRiskViewSet,
    ProjectSectionViewSet,
    ProjectStateLabelViewSet,
    ProjectStatusUpdateViewSet,
    ProjectTemplateViewSet,
    ProjectViewSet,
    WorkflowTransitionViewSet,
)

router = DefaultRouter()
router.register(r"projects", ProjectViewSet, basename="project")
router.register(r"project-status-updates", ProjectStatusUpdateViewSet, basename="project-status-update")
router.register(r"project-risks", ProjectRiskViewSet, basename="project-risk")
router.register(r"project-sections", ProjectSectionViewSet, basename="project-section")
router.register(r"portfolios", PortfolioViewSet, basename="portfolio")
router.register(r"project-templates", ProjectTemplateViewSet, basename="project-template")
router.register(r"state-labels", ProjectStateLabelViewSet, basename="state-label")
router.register(r"workflow-transitions", WorkflowTransitionViewSet, basename="workflow-transition")

urlpatterns = router.urls
