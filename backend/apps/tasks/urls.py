from rest_framework.routers import DefaultRouter

from .views import TaskViewSet, SubtaskViewSet, CommentViewSet

router = DefaultRouter()
router.register(r"tasks", TaskViewSet, basename="task")
router.register(r"subtasks", SubtaskViewSet, basename="subtask")
router.register(r"comments", CommentViewSet, basename="comment")

urlpatterns = router.urls
