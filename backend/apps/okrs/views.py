from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.okrs.models import KeyResult, KeyResultUpdate, Objective
from apps.okrs.serializers import (
    KeyResultSerializer,
    KeyResultUpdateSerializer,
    ObjectiveSerializer,
)


class ObjectiveViewSet(viewsets.ModelViewSet):
    """CRUD for Objectives, scoped to the current user."""

    permission_classes = [IsAuthenticated]
    serializer_class = ObjectiveSerializer

    def get_queryset(self):
        return Objective.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=["get", "post"], url_path="progress")
    def progress(self, request, pk=None):
        """Calculate and (optionally) store the objective progress.

        GET returns the computed progress without persisting it.
        POST persists the computed progress on the objective.
        """
        objective = self.get_object()
        key_results = objective.key_results.all()

        if not key_results.exists():
            computed = 0
        else:
            total = 0.0
            for kr in key_results:
                if kr.target_value:
                    total += min(
                        max(kr.current_value / kr.target_value, 0.0), 1.0
                    )
            computed = round(total / key_results.count() * 100)

        if request.method == "POST":
            objective.progress = computed
            objective.save(update_fields=["progress", "updated_at"])
            serializer = self.get_serializer(objective)
            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response({"progress": computed}, status=status.HTTP_200_OK)


class KeyResultViewSet(viewsets.ModelViewSet):
    """CRUD for Key Results, scoped to the current user."""

    permission_classes = [IsAuthenticated]
    serializer_class = KeyResultSerializer

    def get_queryset(self):
        return KeyResult.objects.filter(
            owner=self.request.user
        ).prefetch_related("linked_tasks")

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=["post"], url_path="update_value")
    def update_value(self, request, pk=None):
        """Add a KeyResultUpdate and update the key result's current_value."""
        key_result = self.get_object()
        new_value = request.data.get("new_value")
        note = request.data.get("note", "")

        if new_value is None:
            return Response(
                {"detail": "new_value is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            new_value = float(new_value)
        except (TypeError, ValueError):
            return Response(
                {"detail": "new_value must be a number."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            # Lock de la fila para que old_value sea consistente bajo
            # escrituras concurrentes
            key_result = type(key_result).objects.select_for_update().get(
                pk=key_result.pk
            )
            old_value = key_result.current_value
            KeyResultUpdate.objects.create(
                key_result=key_result,
                user=request.user,
                old_value=old_value,
                new_value=new_value,
                note=note,
            )
            key_result.current_value = new_value
            key_result.save(update_fields=["current_value"])

        serializer = self.get_serializer(key_result)
        return Response(serializer.data, status=status.HTTP_200_OK)


class KeyResultUpdateViewSet(viewsets.GenericViewSet):
    """List and create KeyResultUpdate records for the current user."""

    permission_classes = [IsAuthenticated]
    serializer_class = KeyResultUpdateSerializer

    def get_queryset(self):
        return KeyResultUpdate.objects.filter(user=self.request.user)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
