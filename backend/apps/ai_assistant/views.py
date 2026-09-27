from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tasks.models import Task

from . import services
from .models import AiSuggestion
from .serializers import AiSuggestionSerializer


class SuggestionListView(generics.ListAPIView):
    """GET /api/ai/suggestions/ — lista las sugerencias del usuario."""

    serializer_class = AiSuggestionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return AiSuggestion.objects.filter(user=self.request.user)


class EstimatePriorityView(APIView):
    """POST /api/ai/estimate-priority/ — {task_id} → {suggested_priority, confidence}."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        task_id = request.data.get("task_id")
        task = get_object_or_404(Task.objects.for_user(request.user).exclude(encrypted_data__isnull=False), id=task_id)
        result = services.estimate_priority(task)

        AiSuggestion.objects.create(
            user=request.user,
            task=task,
            suggestion_type=AiSuggestion.SuggestionType.PRIORITY_ESTIMATE,
            input_data={"task_id": task.id},
            output_data=result,
            confidence=result.get("confidence", 0.0),
        )
        return Response(result, status=status.HTTP_200_OK)


class EstimateStoryPointsView(APIView):
    """POST /api/ai/estimate-story-points/ — {task_id} → {suggested_points, confidence}."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        task_id = request.data.get("task_id")
        task = get_object_or_404(Task.objects.for_user(request.user).exclude(encrypted_data__isnull=False), id=task_id)
        result = services.estimate_story_points(task)

        AiSuggestion.objects.create(
            user=request.user,
            task=task,
            suggestion_type=AiSuggestion.SuggestionType.STORY_POINT_ESTIMATE,
            input_data={"task_id": task.id},
            output_data=result,
            confidence=result.get("confidence", 0.0),
        )
        return Response(result, status=status.HTTP_200_OK)


class DetectBlockersView(APIView):
    """GET /api/ai/detect-blockers/ — devuelve lista de posibles bloqueos."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        blockers = services.detect_blockers(request.user)
        AiSuggestion.objects.create(
            user=request.user,
            task=None,
            suggestion_type=AiSuggestion.SuggestionType.BLOCKER_DETECTION,
            input_data={"user_id": request.user.id},
            output_data={"blockers": blockers},
            confidence=0.8 if blockers else 0.95,
        )
        return Response({"blockers": blockers}, status=status.HTTP_200_OK)


class ImproveDescriptionView(APIView):
    """POST /api/ai/improve-description/ — {task_id} → {suggestions: [...]}."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        task_id = request.data.get("task_id")
        task = get_object_or_404(Task.objects.for_user(request.user).exclude(encrypted_data__isnull=False), id=task_id)
        result = services.improve_description(task)

        AiSuggestion.objects.create(
            user=request.user,
            task=task,
            suggestion_type=AiSuggestion.SuggestionType.DESCRIPTION_IMPROVEMENT,
            input_data={"task_id": task.id, "description": task.description},
            output_data=result,
            confidence=result.get("confidence", 0.0),
        )
        return Response(result, status=status.HTTP_200_OK)


class SuggestionActionView(APIView):
    """POST /api/ai/suggestions/<id>/action/ — aceptar, rechazar o aplicar una sugerencia."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk=None):
        from django.shortcuts import get_object_or_404
        suggestion = get_object_or_404(AiSuggestion, id=pk, user=request.user)
        action = request.data.get("action")  # accept, reject, apply

        if action == "accept":
            suggestion.status = "accepted"
            suggestion.save(update_fields=["status"])
            return Response({"message": "Sugerencia aceptada"})

        elif action == "reject":
            suggestion.status = "rejected"
            suggestion.save(update_fields=["status"])
            return Response({"message": "Sugerencia rechazada"})

        elif action == "apply":
            if not suggestion.task:
                return Response(
                    {"error": "Esta sugerencia no tiene tarea asociada"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            task = suggestion.task
            output = suggestion.output_data or {}

            if suggestion.suggestion_type == AiSuggestion.SuggestionType.PRIORITY_ESTIMATE:
                task.priority = output.get("suggested_priority", task.priority)
                task.save(update_fields=["priority"])
            elif suggestion.suggestion_type == AiSuggestion.SuggestionType.STORY_POINT_ESTIMATE:
                task.story_points = output.get("suggested_points", task.story_points)
                task.save(update_fields=["story_points"])
            elif suggestion.suggestion_type == AiSuggestion.SuggestionType.DESCRIPTION_IMPROVEMENT:
                # Las sugerencias de descripción son orientativas (consejos),
                # no un texto reescrito — no hay nada auto-aplicable.
                return Response(
                    {"error": "Las sugerencias de descripción son orientativas; edita la tarea manualmente"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            suggestion.status = "applied"
            suggestion.save(update_fields=["status"])
            return Response({"message": "Sugerencia aplicada a la tarea"})

        return Response(
            {"error": "Acción no válida. Usa: accept, reject o apply"},
            status=status.HTTP_400_BAD_REQUEST,
        )
