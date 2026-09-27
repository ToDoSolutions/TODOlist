"""Views para colaboración: equipos, miembros, invitaciones, audit."""
import secrets

from django.conf import settings
from django.db.models import Q
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .audit import log_create, log_delete, log_role_change, log_update
from .models import (
    AuditLog,
    ExternalCalendar,
    Invitation,
    Meeting,
    Mention,
    ProjectMember,
    Team,
    TeamMembership,
    Whiteboard,
)
from .serializers import (
    AuditLogSerializer,
    ExternalCalendarSerializer,
    ExternalEventSerializer,
    InvitationSerializer,
    MeetingSerializer,
    MentionSerializer,
    ProjectMemberSerializer,
    TeamMembershipSerializer,
    TeamSerializer,
    WhiteboardSerializer,
)


def _user_is_team_admin(user, team):
    """True si el usuario es owner del equipo o tiene rol owner."""
    return (
        team.owner_id == user.id
        or team.memberships.filter(user=user, role=TeamMembership.Role.OWNER).exists()
    )


def _user_can_manage_project(user, project):
    """True si el usuario puede gestionar miembros del proyecto."""
    return (
        project.owner_id == user.id
        or ProjectMember.objects.filter(
            project=project, user=user, role=ProjectMember.Role.OWNER
        ).exists()
    )


class TeamViewSet(viewsets.ModelViewSet):
    """CRUD de equipos."""
    serializer_class = TeamSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Team.objects.filter(
            models_Q_memberships(self.request.user)
        ).distinct()

    def check_object_permissions(self, request, obj):
        super().check_object_permissions(request, obj)
        # Editar/borrar el equipo requiere ser admin (owner o rol owner).
        # remove_member tiene su propia lógica (admin o self-removal).
        if (
            request.method not in ("GET", "HEAD", "OPTIONS")
            and self.action != "remove_member"
            and not _user_is_team_admin(request.user, obj)
        ):
            self.permission_denied(
                request, message="Solo un admin del equipo puede modificarlo"
            )

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

    def perform_update(self, serializer):
        instance = serializer.instance
        old_values = {
            f: getattr(instance, f)
            for f in serializer.validated_data
            if hasattr(instance, f)
        }
        team = serializer.save()
        new_values = {
            f: getattr(team, f) for f in old_values
        }
        if old_values != new_values:
            log_update(
                actor=self.request.user,
                resource_type="team", resource_id=team.id,
                resource_name=team.name,
                old_values=old_values,
                new_values=new_values,
            )

    def perform_destroy(self, instance):
        log_delete(
            actor=self.request.user,
            resource_type="team", resource_id=instance.id,
            resource_name=instance.name,
            old_values={"name": instance.name, "description": instance.description},
        )
        instance.delete()

    @action(detail=True, methods=["get", "post"])
    def members(self, request, pk=None):
        """Lista o añade miembros del equipo."""
        team = self.get_object()
        if request.method == "GET":
            memberships = team.memberships.all()
            serializer = TeamMembershipSerializer(memberships, many=True)
            return Response(serializer.data)
        # POST: añadir miembro — solo owner/admin del equipo
        if not _user_is_team_admin(request.user, team):
            raise PermissionDenied("Solo el propietario o un admin puede añadir miembros")
        user_id = request.data.get("user_id")
        role = request.data.get("role", "member")
        valid_roles = [r[0] for r in TeamMembership.Role.choices]
        if role not in valid_roles:
            return Response(
                {"error": f"Rol inválido: {role}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Solo el propietario puede nombrar otros owners
        if role == TeamMembership.Role.OWNER and team.owner_id != request.user.id:
            raise PermissionDenied("Solo el propietario puede asignar rol owner")
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
        """Elimina un miembro del equipo (admin o el propio miembro)."""
        team = self.get_object()
        try:
            membership = team.memberships.get(id=member_id)
        except TeamMembership.DoesNotExist:
            return Response(
                {"error": "Miembro no encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )
        is_self = membership.user_id == request.user.id
        if not is_self and not _user_is_team_admin(request.user, team):
            raise PermissionDenied("Solo el propietario o un admin puede eliminar miembros")
        if membership.role == TeamMembership.Role.OWNER and team.owner_id != request.user.id:
            raise PermissionDenied("No puedes eliminar al propietario")
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
        qs = ProjectMember.objects.filter(
            project__owner=self.request.user
        ) | ProjectMember.objects.filter(user=self.request.user)
        project_id = self.request.query_params.get("project")
        if project_id:
            qs = qs.filter(project_id=project_id)
        return qs.distinct()

    def perform_create(self, serializer):
        # Solo quien gestiona el proyecto puede añadir miembros
        project = serializer.validated_data["project"]
        if not _user_can_manage_project(self.request.user, project):
            raise PermissionDenied("No tienes permiso para añadir miembros a este proyecto")
        role = serializer.validated_data.get("role", ProjectMember.Role.VIEWER)
        if role == ProjectMember.Role.OWNER and project.owner_id != self.request.user.id:
            raise PermissionDenied("Solo el propietario puede asignar rol owner")
        member = serializer.save(invited_by=self.request.user)
        log_role_change(
            actor=self.request.user,
            target_user=member.user,
            old_role="none",
            new_role=member.role,
            resource_type="project",
            resource_id=member.project_id,
        )

    def perform_update(self, serializer):
        member = self.get_object()
        # Solo quien gestiona el proyecto puede cambiar roles; nadie puede
        # editar su propia membresía (evitar auto-escalada de rol)
        if not _user_can_manage_project(self.request.user, member.project):
            raise PermissionDenied("No tienes permiso para modificar esta membresía")
        if member.user_id == self.request.user.id and member.project.owner_id != self.request.user.id:
            raise PermissionDenied("No puedes modificar tu propia membresía")
        role = serializer.validated_data.get("role", member.role)
        if role == ProjectMember.Role.OWNER and member.project.owner_id != self.request.user.id:
            raise PermissionDenied("Solo el propietario puede asignar rol owner")
        serializer.save()

    def perform_destroy(self, instance):
        # El propio miembro puede abandonar; si no, hace falta gestión del proyecto
        if instance.user_id != self.request.user.id and not _user_can_manage_project(
            self.request.user, instance.project
        ):
            raise PermissionDenied("No tienes permiso para eliminar este miembro")
        if instance.role == ProjectMember.Role.OWNER and instance.project.owner_id != self.request.user.id:
            raise PermissionDenied("No puedes eliminar al propietario")
        instance.delete()

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
        # Autorización: solo quien gestiona el proyecto puede invitar
        from apps.projects.models import Project
        try:
            project = Project.objects.get(pk=project_id)
        except Project.DoesNotExist:
            return Response(
                {"error": "Proyecto no encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not _user_can_manage_project(request.user, project):
            raise PermissionDenied("No tienes permiso para invitar a este proyecto")
        valid_roles = [r[0] for r in ProjectMember.Role.choices]
        if role not in valid_roles:
            return Response(
                {"error": f"Rol inválido: {role}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if role == ProjectMember.Role.OWNER and project.owner_id != request.user.id:
            raise PermissionDenied("Solo el propietario puede asignar rol owner")
        from apps.users.models import User
        user = User.objects.filter(email__iexact=email).first()
        if not user:
            return Response(
                {"error": "Usuario no encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )
        member, created = ProjectMember.objects.get_or_create(
            project=project, user=user,
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
        """El usuario ve invitaciones que envió Y las que recibió."""
        return Invitation.objects.filter(
            invited_by=self.request.user
        ) | Invitation.objects.filter(email__iexact=self.request.user.email)

    def perform_create(self, serializer):
        from datetime import timedelta
        target_type = serializer.validated_data.get("target_type")
        target_id = serializer.validated_data.get("target_id")
        role = serializer.validated_data.get("role", "member")

        # Validar que el emisor controla el recurso destino
        if target_type == Invitation.TargetType.TEAM:
            try:
                team = Team.objects.get(pk=target_id)
            except Team.DoesNotExist:
                raise ValidationError({"target_id": "Equipo no encontrado"})
            if not _user_is_team_admin(self.request.user, team):
                raise PermissionDenied("No administras este equipo")
            valid_roles = [r[0] for r in TeamMembership.Role.choices]
        elif target_type == Invitation.TargetType.PROJECT:
            from apps.projects.models import Project
            try:
                project = Project.objects.get(pk=target_id)
            except Project.DoesNotExist:
                raise ValidationError({"target_id": "Proyecto no encontrado"})
            if not _user_can_manage_project(self.request.user, project):
                raise PermissionDenied("No administras este proyecto")
            valid_roles = [r[0] for r in ProjectMember.Role.choices]
        else:
            raise ValidationError({"target_type": "Tipo de destino inválido"})

        if role not in valid_roles:
            raise ValidationError({"role": f"Rol inválido: {role}"})

        serializer.save(
            invited_by=self.request.user,
            token=secrets.token_urlsafe(32),
            expires_at=timezone_now() + timedelta(days=7),
        )

    def _get_invitation_for_action(self, request, pk=None):
        """Obtiene la invitación verificando que el usuario es destinatario o emisor."""
        try:
            invitation = Invitation.objects.get(pk=pk)
        except Invitation.DoesNotExist:
            return None, Response(
                {"error": "Invitación no encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )
        # Solo el destinatario o el emisor pueden actuar
        if invitation.email != request.user.email and invitation.invited_by != request.user:
            return None, Response(
                {"error": "No tienes permiso para esta invitación"},
                status=status.HTTP_403_FORBIDDEN,
            )
        return invitation, None

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        """Acepta una invitación. Solo el destinatario (por email)."""
        invitation, error = self._get_invitation_for_action(request, pk)
        if error:
            return error
        if invitation.email.lower() != request.user.email.lower():
            return Response(
                {"error": "Solo el destinatario puede aceptar la invitación"},
                status=status.HTTP_403_FORBIDDEN,
            )
        if invitation.status != "pending":
            return Response(
                {"error": "Invitación ya procesada"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if invitation.expires_at and timezone_now() > invitation.expires_at:
            invitation.status = "expired"
            invitation.save(update_fields=["status"])
            return Response(
                {"error": "La invitación ha expirado"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        invitation.status = "accepted"
        invitation.responded_at = timezone_now()
        invitation.save(update_fields=["status", "responded_at"])
                # Crear la membresía real: sin esto aceptar no daba acceso
        if invitation.target_type == Invitation.TargetType.PROJECT:
            from apps.projects.models import Project
            project = Project.objects.filter(pk=invitation.target_id).first()
            if project:
                role = invitation.role if invitation.role in (
                    ProjectMember.Role.VIEWER, ProjectMember.Role.EDITOR,
                ) else ProjectMember.Role.VIEWER
                ProjectMember.objects.get_or_create(
                    project=project,
                    user=request.user,
                    defaults={"role": role, "invited_by": invitation.invited_by},
                )
        elif invitation.target_type == Invitation.TargetType.TEAM:
            team = Team.objects.filter(pk=invitation.target_id).first()
            if team:
                role = invitation.role if invitation.role in (
                    TeamMembership.Role.MEMBER, TeamMembership.Role.ADMIN,
                ) else TeamMembership.Role.MEMBER
                TeamMembership.objects.get_or_create(
                    team=team,
                    user=request.user,
                    defaults={"role": role},
                )
        return Response({"message": "Invitación aceptada"})

    @action(detail=True, methods=["post"])
    def decline(self, request, pk=None):
        """Rechaza una invitación. Solo el destinatario (por email)."""
        invitation, error = self._get_invitation_for_action(request, pk)
        if error:
            return error
        if invitation.email.lower() != request.user.email.lower():
            return Response(
                {"error": "Solo el destinatario puede rechazar la invitación"},
                status=status.HTTP_403_FORBIDDEN,
            )
        if invitation.status != "pending":
            return Response(
                {"error": "Invitación ya procesada"},
                status=status.HTTP_400_BAD_REQUEST,
            )
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


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def activity_feed(request):
    """Feed global de actividad: TaskActivity + AuditLog unificados.

    Devuelve las últimas entradas ordenadas por fecha desc:
    - TaskActivity: cambios en tareas accesibles por el usuario.
    - AuditLog: acciones de auditoría del propio usuario.
    Cada entrada: {kind, action, actor, resource, summary, created_at}.
    """
    from apps.tasks.models import Task, TaskActivity

    limit = min(int(request.query_params.get("limit", 50)), 200)
    feed = []

    accessible_tasks = Task.objects.for_user(request.user)
    for a in TaskActivity.objects.filter(
        task__in=accessible_tasks
    ).select_related("actor", "task").order_by("-created_at")[:limit]:
        feed.append({
            "kind": "task_activity",
            "action": a.action,
            "actor": a.actor.email if a.actor else None,
            "resource": f"task:{a.task_id}",
            "summary": f"{a.task.title}: {a.action}"
                       + (f" {a.field}" if a.field else ""),
            "created_at": a.created_at.isoformat(),
        })

    for log in AuditLog.objects.filter(
        actor=request.user
    ).order_by("-created_at")[:limit]:
        feed.append({
            "kind": "audit",
            "action": log.action,
            "actor": request.user.email,
            "resource": f"{log.resource_type}:{log.resource_id}",
            "summary": f"{log.action} {log.resource_type} {log.resource_name}",
            "created_at": log.created_at.isoformat(),
        })

    feed.sort(key=lambda e: e["created_at"], reverse=True)
    return Response(feed[:limit])


def _user_can_write_meeting(user, meeting):
    """Escritura sobre la reunión: owner, o escritura en su proyecto.

    Un attendee o un viewer del proyecto solo tienen lectura.
    """
    if meeting.owner_id == user.id:
        return True
    if not meeting.project_id:
        return False
    from apps.projects.models import accessible_projects
    return accessible_projects(user, write=True).filter(
        id=meeting.project_id
    ).exists()


class MeetingViewSet(viewsets.ModelViewSet):
    """Reuniones: notas, decisiones y action items vinculados a tareas.

    POST /api/meetings/{id}/create_task/ {"title": ...} → crea una tarea
    real desde un action item y la vincula a la reunión.
    POST /api/meetings/{id}/video/ → crea (idempotente) la sala Jitsi y
    devuelve {"room", "url"}. POST /{id}/close_video/ la cierra.
    """
    serializer_class = MeetingSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["project"]
    search_fields = ["title", "notes", "decisions"]
    ordering_fields = ["scheduled_at", "created_at"]

    def get_queryset(self):
        from apps.projects.models import accessible_projects
        return Meeting.objects.filter(
            Q(owner=self.request.user)
            | Q(attendees=self.request.user)
            | Q(project__in=accessible_projects(self.request.user))
        ).distinct().select_related("project", "owner").prefetch_related(
            "attendees", "tasks"
        )

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def _get_writable_meeting(self, request):
        """Objeto de la reunión o 404; 403 si solo tiene acceso de lectura."""
        meeting = self.get_object()
        if not _user_can_write_meeting(request.user, meeting):
            raise PermissionDenied(
                "Solo el owner o un editor del proyecto puede gestionar el video"
            )
        return meeting

    @action(detail=True, methods=["post"])
    def create_task(self, request, pk=None):
        """Crea una tarea desde un action item de la reunión."""
        meeting = self.get_object()
        title = request.data.get("title", "").strip()
        if not title:
            return Response(
                {"error": "title requerido"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from apps.tasks.models import Task
        task = Task.objects.create(
            owner=request.user,
            project=meeting.project,
            title=title,
            description=f"Action item de reunión: {meeting.title}",
            state="pending",
        )
        meeting.tasks.add(task)
        return Response(
            {"task_id": task.id, "title": task.title},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def video(self, request, pk=None):
        """Crea la sala Jitsi de la reunión (idempotente) y devuelve la URL.

        Si ``video_room`` ya está seteado devuelve la sala existente sin
        regenerarla — llamadas repetidas retornan la misma sala.
        """
        meeting = self._get_writable_meeting(request)
        if not meeting.video_room:
            meeting.video_room = (
                f"todolist-m{meeting.pk}-{secrets.token_urlsafe(8)}"
            )
            meeting.save(update_fields=["video_room", "updated_at"])
        base = settings.JITSI_BASE_URL.rstrip("/")
        return Response(
            {"room": meeting.video_room, "url": f"{base}/{meeting.video_room}"}
        )

    @action(detail=True, methods=["post"])
    def close_video(self, request, pk=None):
        """Cierra la sala de video (reunión terminada): limpia video_room."""
        meeting = self._get_writable_meeting(request)
        if meeting.video_room:
            meeting.video_room = ""
            meeting.save(update_fields=["video_room", "updated_at"])
        return Response({"room": "", "url": None})


def _user_is_org_admin(user, org):
    """True si el usuario es owner o admin de la organización."""
    from .models import OrganizationMembership
    return (
        org.owner_id == user.id
        or org.memberships.filter(
            user=user,
            role__in=[OrganizationMembership.Role.OWNER, OrganizationMembership.Role.ADMIN],
        ).exists()
    )


class OrganizationViewSet(viewsets.ModelViewSet):
    """CRUD de organizaciones (tenant raíz)."""
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        from .serializers import OrganizationSerializer
        return OrganizationSerializer

    def get_queryset(self):
        from .models import Organization
        return Organization.objects.filter(
            Q(owner=self.request.user) | Q(memberships__user=self.request.user)
        ).distinct()

    def check_object_permissions(self, request, obj):
        super().check_object_permissions(request, obj)
        if (
            request.method not in ("GET", "HEAD", "OPTIONS")
            and self.action not in ("members", "remove_member")
            and not _user_is_org_admin(request.user, obj)
        ):
            self.permission_denied(
                request, message="Solo un admin de la organización puede modificarla"
            )

    def perform_create(self, serializer):
        from .models import OrganizationMembership
        org = serializer.save(owner=self.request.user)
        OrganizationMembership.objects.create(
            organization=org, user=self.request.user,
            role=OrganizationMembership.Role.OWNER,
        )
        log_create(self.request.user, "organization", org.id, org.name)

    def perform_update(self, serializer):
        instance = self.get_object()
        old = {f: getattr(instance, f) for f in ("name", "description")}
        org = serializer.save()
        log_update(self.request.user, "organization", org.id, org.name, old, {
            "name": org.name, "description": org.description,
        })

    def perform_destroy(self, instance):
        log_delete(self.request.user, "organization", instance.id, instance.name)
        instance.delete()

    @action(detail=True, methods=["post"])
    def add_member(self, request, pk=None):
        """Añade un miembro a la organización (admin only)."""
        org = self.get_object()
        if not _user_is_org_admin(request.user, org):
            raise PermissionDenied("Solo un admin puede añadir miembros")
        from django.contrib.auth import get_user_model

        from .models import OrganizationMembership
        user = get_user_model().objects.filter(
            email=request.data.get("email", "")
        ).first()
        if not user:
            raise ValidationError("Usuario no encontrado")
        role = request.data.get("role", OrganizationMembership.Role.MEMBER)
        if role not in [c[0] for c in OrganizationMembership.Role.choices]:
            raise ValidationError("Rol inválido")
        OrganizationMembership.objects.update_or_create(
            organization=org, user=user, defaults={"role": role}
        )
        log_role_change(request.user, user, None, role, resource_type="organization", resource_id=org.id)
        return Response({"message": f"{user.email} añadido como {role}"})

    @action(detail=True, methods=["post"])
    def remove_member(self, request, pk=None):
        """Elimina un miembro (admin, o self-removal)."""
        org = self.get_object()
        from .models import OrganizationMembership
        uid = request.data.get("user_id")
        is_self = str(uid) == str(request.user.id)
        if not is_self and not _user_is_org_admin(request.user, org):
            raise PermissionDenied("Solo un admin puede eliminar miembros")
        deleted, _ = OrganizationMembership.objects.filter(
            organization=org, user_id=uid
        ).delete()
        if not deleted:
            raise ValidationError("El usuario no es miembro")
        return Response({"message": "Miembro eliminado"})


def _parse_range_param(value):
    """Parsea un query param de fecha/datetime a un datetime aware (o None)."""
    if not value:
        return None
    import datetime as dt

    from django.utils import timezone
    from django.utils.dateparse import parse_date, parse_datetime

    parsed = parse_datetime(value)
    if parsed is None:
        d = parse_date(value)
        if d is not None:
            parsed = dt.datetime.combine(d, dt.time.min)
    if parsed is not None and timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, dt.UTC)
    return parsed


class ExternalCalendarViewSet(viewsets.ModelViewSet):
    """CRUD de calendarios externos (feed iCal inbound), owner-scoped.

    POST /api/external-calendars/{id}/refresh/ → sync manual inmediata.
    GET  /api/external-calendars/{id}/events/?start&end → eventos en rango.
    """

    serializer_class = ExternalCalendarSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ExternalCalendar.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["post"])
    def refresh(self, request, pk=None):
        """Fuerza una sincronización del feed (síncrona)."""
        from .tasks import sync_external_calendar

        calendar = self.get_object()
        count = sync_external_calendar(calendar)
        calendar.refresh_from_db()
        data = self.get_serializer(calendar).data
        data["events_imported"] = count
        return Response(data)

    @action(detail=True, methods=["get"])
    def events(self, request, pk=None):
        """Eventos del calendario que solapan el rango [start, end]."""
        calendar = self.get_object()
        qs = calendar.events.all()
        start = _parse_range_param(request.query_params.get("start"))
        end = _parse_range_param(request.query_params.get("end"))
        if start is not None:
            qs = qs.filter(
                Q(dtend__gte=start)
                | Q(dtend__isnull=True, dtstart__gte=start)
            )
        if end is not None:
            qs = qs.filter(dtstart__lte=end)
        return Response(ExternalEventSerializer(qs, many=True).data)


class WhiteboardViewSet(viewsets.ModelViewSet):
    """CRUD de pizarras colaborativas por proyecto.

    GET: pizarras de proyectos con acceso de lectura.
    Mutaciones: solo proyectos donde el usuario tiene escritura
    (owner/editor). PATCH soporta actualizaciones parciales de ``content``.
    """

    serializer_class = WhiteboardSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["project"]
    search_fields = ["name"]

    def get_queryset(self):
        from apps.projects.models import accessible_projects
        write = self.action in (
            "create", "update", "partial_update", "destroy",
        )
        return Whiteboard.objects.filter(
            project__in=accessible_projects(self.request.user, write=write)
        ).select_related("project", "owner")

    def perform_create(self, serializer):
        from apps.projects.models import accessible_projects
        project = serializer.validated_data.get("project")
        if not project or not accessible_projects(
            self.request.user, write=True
        ).filter(id=project.id).exists():
            raise PermissionDenied(
                "Solo owner/editor del proyecto puede crear pizarras"
            )
        serializer.save(owner=self.request.user)
