from django.urls import path

from .views import (
    DetectBlockersView,
    EstimatePriorityView,
    EstimateStoryPointsView,
    ImproveDescriptionView,
    SuggestionActionView,
    SuggestionListView,
)

urlpatterns = [
    path("ai/suggestions/", SuggestionListView.as_view(), name="ai_suggestions_list"),
    path("ai/suggestions/<int:pk>/action/", SuggestionActionView.as_view(), name="ai_suggestion_action"),
    path("ai/estimate-priority/", EstimatePriorityView.as_view(), name="ai_estimate_priority"),
    path("ai/estimate-story-points/", EstimateStoryPointsView.as_view(), name="ai_estimate_story_points"),
    path("ai/detect-blockers/", DetectBlockersView.as_view(), name="ai_detect_blockers"),
    path("ai/improve-description/", ImproveDescriptionView.as_view(), name="ai_improve_description"),
]
