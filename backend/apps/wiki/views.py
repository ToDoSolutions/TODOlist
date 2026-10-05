from django.core.exceptions import PermissionDenied
from django.db.models import Q
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

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
        write = self.action in (
            "create", "update", "partial_update", "destroy", "restore"
        )
        projects = accessible_projects(self.request.user, write=write)
        from django.db.models import Count
        return WikiPage.objects.filter(
            Q(owner=self.request.user) | Q(project__in=projects)
        ).select_related("project", "parent", "updated_by").annotate(
            children_count_ann=Count("children", distinct=True)
        )

    def check_object_permissions(self, request, obj):
        """Escritura sobre páginas de proyecto requiere rol owner/editor."""
        super().check_object_permissions(request, obj)
        if (
            request.method in ("PUT", "PATCH", "DELETE", "POST")
            and self.action != "create"
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

    @action(detail=True, methods=["get"])
    def revisions(self, request, pk=None):
        """Historial de versiones de la página (lectura)."""
        page = self.get_object()
        return Response(
            [
                {
                    "version": r.version,
                    "title": r.title,
                    "edited_by": r.edited_by_id,
                    "created_at": r.created_at,
                }
                for r in page.revisions.all()
            ]
        )

    @action(detail=True, methods=["get"], url_path=r"revisions/(?P<version>\d+)")
    def revision_detail(self, request, pk=None, version=None):
        """Contenido de una revisión concreta (para diffs/preview)."""
        page = self.get_object()
        r = page.revisions.filter(version=version).first()
        if r is None:
            return Response({"detail": "Revisión no encontrada"}, status=404)
        return Response(
            {
                "version": r.version,
                "title": r.title,
                "content": r.content,
                "edited_by": r.edited_by_id,
                "created_at": r.created_at,
            }
        )

    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        """Restaura la página a una revisión: body {"version": N}.

        Crea una nueva revisión con el contenido restaurado (la
        historia nunca se reescribe). Requiere escritura: el queryset
        para POST ya filtra por proyectos editables + check_object.
        """
        page = self.get_object()
        version = request.data.get("version")
        r = page.revisions.filter(version=version).first()
        if r is None:
            return Response({"detail": "Revisión no encontrada"}, status=404)
        page.title = r.title
        page.content = r.content
        page.updated_by = request.user
        page.save()
        return Response(WikiPageSerializer(page).data)
