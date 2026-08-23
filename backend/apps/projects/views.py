from rest_framework import viewsets

from .models import Project
from .serializers import ProjectSerializer


class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer
    filterset_fields = ["is_archived"]
    search_fields = ["name", "description"]
    ordering_fields = ["created_at", "updated_at", "name"]

    def get_queryset(self):
        qs = Project.objects.filter(owner=self.request.user)
        archived = self.request.query_params.get("archived")
        if archived is None:
            qs = qs.filter(is_archived=False)
        return qs

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)
