"""Views para colaboración: equipos, miembros, invitaciones, audit."""
import secrets
from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import (
    Team, TeamMembership, ProjectMember, Invitation, Mention, AuditLog,
)
from .serializers import (
    TeamSerializer, TeamMembershipSerializer, ProjectMemberSerializer,
    InvitationSerializer, MentionSerializer, AuditLogSerializer,
)
from .audit import log_create, log_delete, log_role_change


class TeamViewSet(viewsets.ModelViewSet):
    """CRUD de equipos."""
    serializer_class = TeamSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Team.objects.filter(
            models_Q_memberships(self.request.user)
        ).distinct()

    def perform_create(self, serializer):
        team = serializer.save(owner=self.request.user)
        # El creador es owner del equipo
        TeamMembership.objects.create(
            team=team, user=self.request.user, role=TeamMembership.Role.OWNER
        )
        log_create(
            actor=self.request.user,
            resource_type="team", resource_id=team.id,
            resource_name=team.name,
        )

    @action(detail=True, methods=["get", "post"])
    def members(self, request, pk=None):
        """Lista o añade miembros del equipo."""
        team = self.get_object()
        if request.method == "GET":
            memberships = team.memberships.all()
            serializer = TeamMembershipSerializer(memberships, many=True)
            return Response(serializer.data)
        # POST: añadir miembro
        user_id = request.data.get("user_id")
        role = request.data.get("role", "member")
        if not user_id:
            return Response(
                {"error": "user_id requerido"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from apps.users.models import User
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"error": "Usuario no encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )
        membership, created = TeamMembership.objects.get_or_create(
            team=team, user=user,
            defaults={"role": role},
        )
        if not created:
            return Response(
                {"error": "Ya es miembro"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            TeamMembershipSerializer(membership).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["delete"], url_path=r"members/(?P<member_id>\d+)")
    def remove_member(self, request, pk=None, member_id=None):
        """Elimina un miembro del equipo."""
        team = self.get_object()
        try:
            membership = team.memberships.get(id=member_id)
        except TeamMembership.DoesNotExist:
            return Response(
                {"error": "Miembro no encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )
        membership.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def models_Q_memberships(user):
    """Helper para filtrar equipos donde el usuario es miembro."""
    from django.db.models import Q
    return Q(memberships__user=user) | Q(owner=user)


class ProjectMemberViewSet(viewsets.ModelViewSet):
    """Gestión de miembros de proyecto."""
    serializer_class = ProjectMemberSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ProjectMember.objects.filter(
            project__owner=self.request.user
        ) | ProjectMember.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        member = serializer.save(invited_by=self.request.user)
        log_role_change(
            actor=self.request.user,
            target_user=member.user,
            old_role="none",
            new_role=member.role,
            resource_type="project",
            resource_id=member.project_id,
        )

    @action(detail=False, methods=["post"])
    def invite(self, request):
        """Invita a un usuario a un proyecto por email."""
        email = request.data.get("email")
        project_id = request.data.get("project_id")
        role = request.data.get("role", "viewer")
        if not email or not project_id:
            return Response(
                {"error": "email y project_id requeridos"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from apps.users.models import User
        user = User.objects.filter(email__iexact=email).first()
        if not user:
            return Response(
                {"error": "Usuario no encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )
        member, created = ProjectMember.objects.get_or_create(
            project_id=project_id, user=user,
            defaults={"role": role, "invited_by": request.user},
        )
        if not created:
            return Response(
                {"error": "Ya es miembro del proyecto"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            ProjectMemberSerializer(member).data,
            status=status.HTTP_201_CREATED,
        )


class InvitationViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """Gestión de invitaciones."""
    serializer_class = InvitationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Invitation.objects.filter(invited_by=self.request.user)

    def perform_create(self, serializer):
        serializer.save(
            invited_by=self.request.user,
            token=secrets.token_urlsafe(32),
        )

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        """Acepta una invitación."""
        invitation = self.get_object()
        if invitation.status != "pending":
            return Response(
                {"error": "Invitación ya procesada"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        invitation.status = "accepted"
        invitation.responded_at = timezone_now()
        invitation.save(update_fields=["status", "responded_at"])
        return Response({"message": "Invitación aceptada"})

    @action(detail=True, methods=["post"])
    def decline(self, request, pk=None):
        """Rechaza una invitación."""
        invitation = self.get_object()
        invitation.status = "declined"
        invitation.responded_at = timezone_now()
        invitation.save(update_fields=["status", "responded_at"])
        return Response({"message": "Invitación rechazada"})


class MentionViewSet(
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """Lista de menciones recibidas."""
    serializer_class = MentionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Mention.objects.filter(mentioned_user=self.request.user)


class AuditLogViewSet(
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """Log de auditoría (solo para el propio usuario)."""
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = AuditLog.objects.filter(actor=self.request.user)
        # Filtros opcionales
        action = self.request.query_params.get("action")
        if action:
            qs = qs.filter(action=action)
        resource_type = self.request.query_params.get("resource_type")
        if resource_type:
            qs = qs.filter(resource_type=resource_type)
        return qs[:100]


def timezone_now():
    from django.utils import timezone
    return timezone.now()
