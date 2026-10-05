from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import (
    action,
    api_view,
    permission_classes,
    throttle_classes,
)
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.users.api_auth import PublicShareRateThrottle

from .models import Dashboard, ShareLink
from .resolver import WIDGET_TYPES, resolve_widget
from .serializers import DashboardSerializer, ShareLinkSerializer


class DashboardViewSet(viewsets.ModelViewSet):
    """Dashboards personalizables del usuario.

    GET /api/dashboards/{id}/data/ → resuelve todos los widgets con datos
    reales. GET /api/dashboards/widget-types/ → catálogo de tipos.
    POST /api/dashboards/{id}/share/ {email} → comparte lectura con un
    usuario; los datos se resuelven con el scope de quien consulta.
    """
    serializer_class = DashboardSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        u = self.request.user
        return Dashboard.objects.filter(
            Q(owner=u) | Q(shared_with=u)
        ).distinct().prefetch_related("shared_with")

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def _require_owner(self, dashboard):
        if dashboard.owner_id != self.request.user.id:
            raise PermissionDenied("Solo el propietario puede modificar este dashboard.")

    def update(self, request, *args, **kwargs):
        self._require_owner(self.get_object())
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        self._require_owner(self.get_object())
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        self._require_owner(self.get_object())
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["get"])
    def data(self, request, pk=None):
        """Resuelve cada widget del dashboard con sus datos actuales."""
        dashboard = self.get_object()
        resolved = []
        for w in dashboard.widgets:
            resolved.append({
                "id": w.get("id"),
                "type": w.get("type"),
                "title": w.get("title"),
                "size": w.get("size"),
                "data": resolve_widget(request.user, w),
            })
        return Response({
            "dashboard": dashboard.name,
            "widgets": resolved,
        })

    @action(detail=False, methods=["get"])
    def widget_types(self, request):
        """Catálogo de tipos de widget disponibles."""
        return Response(sorted(WIDGET_TYPES))

    @action(detail=True, methods=["post"])
    def share(self, request, pk=None):
        """Comparte el dashboard (lectura) con otro usuario por email."""
        dashboard = self.get_object()
        self._require_owner(dashboard)
        email = (request.data.get("email") or "").strip().lower()
        if not email:
            return Response({"error": "email requerido"}, status=status.HTTP_400_BAD_REQUEST)
        User = get_user_model()
        try:
            target = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return Response({"error": "Usuario no encontrado"}, status=status.HTTP_404_NOT_FOUND)
        if target.id == request.user.id:
            return Response({"error": "No puedes compartir contigo mismo"}, status=status.HTTP_400_BAD_REQUEST)
        dashboard.shared_with.add(target)
        return Response(self.get_serializer(dashboard).data)

    @action(detail=True, methods=["post"])
    def unshare(self, request, pk=None):
        """Retira el acceso compartido de un usuario."""
        dashboard = self.get_object()
        self._require_owner(dashboard)
        email = (request.data.get("email") or "").strip().lower()
        User = get_user_model()
        try:
            target = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return Response({"error": "Usuario no encontrado"}, status=status.HTTP_404_NOT_FOUND)
        dashboard.shared_with.remove(target)
        return Response(self.get_serializer(dashboard).data)


class ShareLinkViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Enlaces públicos de proyectos creados por el usuario.

    POST /api/share-links/ {project} → crea el enlace (requiere acceso
    de escritura al proyecto). GET lista solo los propios.
    DELETE /api/share-links/{id}/ → revoca (is_active=False).
    """
    serializer_class = ShareLinkSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ShareLink.objects.filter(
            created_by=self.request.user
        ).select_related("project")

    def perform_create(self, serializer):
        from apps.projects.models import accessible_projects
        project = serializer.validated_data["project"]
        if not accessible_projects(
            self.request.user, write=True
        ).filter(pk=project.pk).exists():
            raise PermissionDenied(
                "Necesitas acceso de escritura al proyecto para compartirlo"
            )
        serializer.save(created_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        """Revoca el enlace (soft-delete): el token deja de resolver."""
        link = self.get_object()
        link.is_active = False
        link.save(update_fields=["is_active"])
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
@permission_classes([AllowAny])
@throttle_classes([PublicShareRateThrottle])
def public_share(request, token):
    """GET /api/public/share/{token}/ — vista pública de solo lectura.

    Devuelve el proyecto y sus tareas no archivadas. 404 si el token no
    existe o el enlace fue revocado.
    """
    link = (
        ShareLink.objects
        .filter(token=token, is_active=True)
        .select_related("project")
        .first()
    )
    if link is None:
        return Response(
            {"error": "Enlace no encontrado"},
            status=status.HTTP_404_NOT_FOUND,
        )
    project = link.project
    from django.db.models import Q
    tasks = (
        # Multi-homing: canónicas + homeadas (misma semilla que ?project=)
        project.tasks.model.objects.filter(
            Q(project=project) | Q(extra_projects=project)
        )
        .exclude(state="archived")
        .select_related("assignee")
        .order_by("-created_at")
        .distinct()
    )
    return Response({
        "project": {
            "id": project.id,
            "name": project.name,
            "description": project.description,
        },
        "tasks": [
            {
                "id": t.id,
                "title": t.title,
                "state": t.state,
                "priority": t.priority,
                "due_date": t.due_date,
                # PII: el enlace público expone el nombre visible, no el
                # email del asignado.
                "assignee_name": (
                    t.assignee.first_name or t.assignee.username
                    if t.assignee else None
                ),
            }
            for t in tasks
        ],
    })
