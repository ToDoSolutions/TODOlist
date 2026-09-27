from rest_framework.routers import DefaultRouter

from .views import (
    AttachmentViewSet,
    CommentViewSet,
    CustomFieldValueViewSet,
    CustomFieldViewSet,
    EpicViewSet,
    OutgoingWebhookViewSet,
    RecurrenceRuleViewSet,
    SavedSearchViewSet,
    SprintViewSet,
    SubtaskViewSet,
    TaskRelationViewSet,
    TaskTemplateViewSet,
    TaskViewSet,
    TimeEntryViewSet,
)

router = DefaultRouter()
router.register(r"tasks", TaskViewSet, basename="task")
router.register(r"subtasks", SubtaskViewSet, basename="subtask")
router.register(r"comments", CommentViewSet, basename="comment")
router.register(r"sprints", SprintViewSet, basename="sprint")
router.register(r"epics", EpicViewSet, basename="epic")
router.register(r"saved-searches", SavedSearchViewSet, basename="saved-search")
router.register(r"task-relations", TaskRelationViewSet, basename="task-relation")
router.register(r"time-entries", TimeEntryViewSet, basename="time-entry")
router.register(r"attachments", AttachmentViewSet, basename="attachment")
router.register(r"task-templates", TaskTemplateViewSet, basename="task-template")
router.register(r"custom-fields", CustomFieldViewSet, basename="custom-field")
router.register(r"custom-field-values", CustomFieldValueViewSet, basename="custom-field-value")
router.register(r"outgoing-webhooks", OutgoingWebhookViewSet, basename="outgoing-webhook")
router.register(r"recurrence-rules", RecurrenceRuleViewSet, basename="recurrence-rule")

urlpatterns = router.urls
