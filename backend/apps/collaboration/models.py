"""Modelos para colaboración: equipos, roles, miembros y menciones."""
from django.conf import settings
from django.db import models


class Team(models.Model):
    """Equipo de trabajo que agrupa usuarios y proyectos."""

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.TextField(blank=True, default="")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_teams",
    )
    avatar = models.ImageField(upload_to="team_avatars/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class TeamMembership(models.Model):
    """Membresía de un usuario en un equipo con un rol."""

    class Role(models.TextChoices):
        OWNER = "owner", "Propietario"
        ADMIN = "admin", "Administrador"
        MEMBER = "member", "Miembro"
        GUEST = "guest", "Invitado"

    team = models.ForeignKey(
        Team, on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="team_memberships",
    )
    role = models.CharField(
        max_length=20, choices=Role.choices, default=Role.MEMBER
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("team", "user")
        ordering = ["-joined_at"]

    def __str__(self):
        return f"{self.user.email} @ {self.team.name} ({self.role})"


class ProjectMember(models.Model):
    """Miembro de un proyecto con rol y permisos específicos.

    Permite compartir proyectos con usuarios sin necesidad de un equipo.
    """

    class Role(models.TextChoices):
        OWNER = "owner", "Propietario"
        EDITOR = "editor", "Editor"
        VIEWER = "viewer", "Lectura"

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="members",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="project_memberships",
    )
    role = models.CharField(
        max_length=20, choices=Role.choices, default=Role.VIEWER
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_invitations",
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("project", "user")
        ordering = ["-joined_at"]

    def __str__(self):
        return f"{self.user.email} @ {self.project.name} ({self.role})"

    @property
    def can_edit(self):
        return self.role in (self.Role.OWNER, self.Role.EDITOR)

    @property
    def can_delete(self):
        return self.role == self.Role.OWNER


class Invitation(models.Model):
    """Invitación a unirse a un equipo o proyecto."""

    class TargetType(models.TextChoices):
        TEAM = "team", "Equipo"
        PROJECT = "project", "Proyecto"

    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        ACCEPTED = "accepted", "Aceptada"
        DECLINED = "declined", "Rechazada"
        EXPIRED = "expired", "Expirada"

    target_type = models.CharField(max_length=20, choices=TargetType.choices)
    target_id = models.IntegerField()
    email = models.EmailField()
    role = models.CharField(max_length=20, default="member")
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="invitations_sent",
    )
    token = models.CharField(max_length=100, unique=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Invite {self.email} to {self.target_type}:{self.target_id}"


class Mention(models.Model):
    """Mención de un usuario en un comentario o tarea."""

    comment = models.ForeignKey(
        "tasks.Comment",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="mentions",
    )
    task = models.ForeignKey(
        "tasks.Task",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="mentions",
    )
    mentioned_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mentions_received",
    )
    mentioned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mentions_made",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.mentioned_by} → {self.mentioned_user}"


class AuditLog(models.Model):
    """Log de auditoría para cambios sensibles.

    Registra acciones como: login, creación/eliminación de proyectos,
    cambios de rol, eliminación de tareas, cambios de configuración, etc.
    """

    class Action(models.TextChoices):
        LOGIN = "login", "Inicio de sesión"
        LOGOUT = "logout", "Cierre de sesión"
        LOGIN_FAILED = "login_failed", "Login fallido"
        CREATE = "create", "Creación"
        UPDATE = "update", "Actualización"
        DELETE = "delete", "Eliminación"
        PERMISSION_CHANGE = "permission_change", "Cambio de permisos"
        ROLE_CHANGE = "role_change", "Cambio de rol"
        EXPORT = "export", "Exportación"
        SETTINGS_CHANGE = "settings_change", "Cambio de configuración"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_actions",
    )
    action = models.CharField(max_length=30, choices=Action.choices)
    # Recurso afectado (genérico)
    resource_type = models.CharField(max_length=50)  # project, task, user, etc.
    resource_id = models.IntegerField(null=True, blank=True)
    resource_name = models.CharField(max_length=255, blank=True, default="")
    # Detalles del cambio
    old_values = models.JSONField(default=dict, blank=True)
    new_values = models.JSONField(default=dict, blank=True)
    # Metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["actor", "-created_at"]),
            models.Index(fields=["resource_type", "resource_id"]),
            models.Index(fields=["action"]),
        ]

    def __str__(self):
        return f"{self.actor} {self.action} {self.resource_type}:{self.resource_id}"
