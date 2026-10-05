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

    def save(self, *args, **kwargs):
        if not self.slug:
            import secrets

            from django.utils.text import slugify
            base = slugify(self.name)[:100] or "team"
            # Sufijo aleatorio corto para evitar colisiones y race conditions
            self.slug = f"{base}-{secrets.token_hex(4)}"
        super().save(*args, **kwargs)

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
    expires_at = models.DateTimeField(null=True, blank=True)
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


class Meeting(models.Model):
    """Reunión con decisiones y action items vinculados a tareas.

    Cierra el ciclo Reunión → Decisiones → Acciones → Tareas: las notas y
    decisiones quedan registradas y cada action item puede crear una tarea
    real enlazada a la reunión.
    """

    title = models.CharField(max_length=255)
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="meetings",
        null=True,
        blank=True,
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="meetings",
    )
    scheduled_at = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField(default=30)
    attendees = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True,
        related_name="meetings_attended",
    )
    notes = models.TextField(blank=True, default="")
    decisions = models.TextField(blank=True, default="")
    # Sala de videoconferencia Jitsi: solo el slug; la URL completa se
    # compone con settings.JITSI_BASE_URL (serializer + action `video`).
    video_room = models.CharField(max_length=80, blank=True, default="")
    # Action items: tareas generadas desde la reunión
    tasks = models.ManyToManyField(
        "tasks.Task", blank=True, related_name="meetings"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-scheduled_at"]

    def __str__(self):
        return f"{self.title} ({self.scheduled_at:%Y-%m-%d})"


class Organization(models.Model):
    """Tenant raíz opcional: agrupa proyectos y equipos.

    Cuando Project.organization está seteada, los miembros de la org acceden
    según su rol (owner/admin → escritura, member → lectura, guest → sin
    acceso implícito). Sin organización el comportamiento es el de siempre
    (owner + ProjectMember).
    """

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.TextField(blank=True, default="")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_organizations",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # SCIM 2.0: la organización es el recurso Group (provisión de
    # membresías desde el IdP). scim_id estable = pk en string.
    scim_id = models.CharField(max_length=254, null=True, blank=True, unique=True)
    scim_external_id = models.CharField(max_length=254, null=True, blank=True, db_index=True)
    scim_display_name = models.CharField(max_length=254, null=True, blank=True, db_index=True)
    # SSO por dominio (enterprise): si sso_required está activo, un login
    # por contraseña para un email @sso_domain se rechaza con 403 — solo
    # vale SSO (OIDC/SAML). El claim del dominio lo hace el admin de la org.
    sso_domain = models.CharField(max_length=253, null=True, blank=True, db_index=True)
    sso_required = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.slug:
            import secrets

            from django.utils.text import slugify
            base = slugify(self.name)[:100] or "org"
            self.slug = f"{base}-{secrets.token_hex(4)}"
        if self.sso_domain:
            self.sso_domain = self.sso_domain.strip().lower().lstrip("@")
        super().save(*args, **kwargs)
        # SCIM: ids/display estables para lookup del IdP.
        updates = {}
        if not self.scim_id:
            updates["scim_id"] = str(self.pk)
        if not self.scim_display_name:
            updates["scim_display_name"] = self.name
        if updates:
            type(self).objects.filter(pk=self.pk).update(**updates)
            for k, v in updates.items():
                setattr(self, k, v)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class OrganizationMembership(models.Model):
    """Membresía de usuario en una organización con rol global."""

    class Role(models.TextChoices):
        OWNER = "owner", "Propietario"
        ADMIN = "admin", "Administrador"
        MEMBER = "member", "Miembro"
        GUEST = "guest", "Invitado"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organization_memberships",
    )
    role = models.CharField(
        max_length=20, choices=Role.choices, default=Role.MEMBER
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("organization", "user")

    def __str__(self):
        return f"{self.user.email} en {self.organization.name} ({self.role})"


class ExternalCalendar(models.Model):
    """Calendario externo suscrito via feed iCal (inbound).

    El usuario pega la URL .ics de otro servicio (Google, Outlook, etc.) y
    sus VEVENTs se sincronizan periódicamente a ``ExternalEvent`` para
    mostrarlos junto a los deadlines locales.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="external_calendars",
    )
    name = models.CharField(max_length=200)
    url = models.URLField(max_length=500)
    color = models.CharField(max_length=7, default="#4caf50")
    is_active = models.BooleanField(default=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.user.email})"


class ExternalEvent(models.Model):
    """Evento sincronizado desde un feed iCal externo.

    Se borran y recrean en cada sync (el feed es la fuente de verdad).
    """

    calendar = models.ForeignKey(
        ExternalCalendar, on_delete=models.CASCADE, related_name="events"
    )
    uid = models.CharField(max_length=255)
    summary = models.CharField(max_length=500, blank=True, default="")
    dtstart = models.DateTimeField()
    dtend = models.DateTimeField(null=True, blank=True)
    all_day = models.BooleanField(default=False)

    class Meta:
        ordering = ["dtstart"]
        indexes = [
            models.Index(fields=["calendar", "dtstart"]),
        ]

    def __str__(self):
        return f"{self.summary} @ {self.dtstart}"


def _default_whiteboard_content():
    return {"nodes": [], "edges": []}


class Whiteboard(models.Model):
    """Pizarra colaborativa por proyecto.

    ``content`` se guarda opaco: el cliente define el shape
    (nodes: {id,x,y,text,color,w,h}; edges: {from,to}).
    """

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="whiteboards",
    )
    name = models.CharField(max_length=200)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="whiteboards",
    )
    content = models.JSONField(default=_default_whiteboard_content)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.name} @ {self.project.name}"
