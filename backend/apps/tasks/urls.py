from rest_framework.routers import DefaultRouter

from .views import (
    TaskViewSet, SubtaskViewSet, CommentViewSet,
    SprintViewSet, EpicViewSet, SavedSearchViewSet,
    TaskRelationViewSet,
)

router = DefaultRouter()
router.register(r"tasks", TaskViewSet, basename="task")
router.register(r"subtasks", SubtaskViewSet, basename="subtask")
router.register(r"comments", CommentViewSet, basename="comment")
router.register(r"sprints", SprintViewSet, basename="sprint")
router.register(r"epics", EpicViewSet, basename="epic")
router.register(r"saved-searches", SavedSearchViewSet, basename="saved-search")
router.register(r"task-relations", TaskRelationViewSet, basename="task-relation")

urlpatterns = router.urls
