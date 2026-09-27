from django.core.exceptions import PermissionDenied
from django.db.models import Q
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.projects.models import accessible_projects

from .models import WikiPage
from .serializers import WikiPageSerializer


class WikiPageViewSet(viewsets.ModelViewSet):
    """CRUD de páginas wiki.

    Lectura: páginas propias + de proyectos accesibles (cualquier rol).
    Escritura: páginas propias sin proyecto, o de proyectos donde el
    usuario es owner/editor. Los viewers solo leen.
    """

    serializer_class = WikiPageSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["project", "parent", "is_published"]
    search_fields = ["title", "content"]
    ordering_fields = ["title", "created_at", "updated_at"]

    def get_queryset(self):
        write = self.action in ("create", "update", "partial_update", "destroy")
        projects = accessible_projects(self.request.user, write=write)
        return WikiPage.objects.filter(
            Q(owner=self.request.user) | Q(project__in=projects)
        ).select_related("project", "parent", "updated_by")

    def check_object_permissions(self, request, obj):
        """Escritura sobre páginas de proyecto requiere rol owner/editor."""
        super().check_object_permissions(request, obj)
        if (
            request.method in ("PUT", "PATCH", "DELETE")
            and obj.project
            and obj.owner_id != request.user.id
        ):
            editable = accessible_projects(
                request.user, write=True
            ).filter(id=obj.project_id).exists()
            if not editable:
                raise PermissionDenied(
                    "Solo owner/editor del proyecto puede modificar esta página"
                )

    def perform_create(self, serializer):
        # El proyecto del payload debe ser editable por el usuario
        # (un viewer no puede crear páginas en un proyecto ajeno).
        project = serializer.validated_data.get("project")
        if project and not accessible_projects(
            self.request.user, write=True
        ).filter(id=project.id).exists():
            raise PermissionDenied(
                "Solo owner/editor del proyecto puede crear páginas"
            )
        serializer.save(owner=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)
