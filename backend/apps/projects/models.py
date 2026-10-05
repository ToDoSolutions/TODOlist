from django.conf import settings
from django.db import models


class Project(models.Model):
    """Proyecto que agrupa tareas. Puede archivarse."""

    class Health(models.TextChoices):
        ON_TRACK = "on_track", "En camino"
        AT_RISK = "at_risk", "En riesgo"
        OFF_TRACK = "off_track", "Desviado"

    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, default="")
    color = models.CharField(max_length=7, default="#1976d2")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="projects",
    )
    organization = models.ForeignKey(
        "collaboration.Organization",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="projects",
        help_text="Tenant opcional: los miembros de la org heredan acceso",
    )
    is_archived = models.BooleanField(default=False)
    # Prefijo para refs legibles de tareas (estilo Linear/Jira: "MP-12").
    # Si se deja en blanco se deriva del nombre al crear el proyecto.
    issue_prefix = models.CharField(max_length=6, blank=True, default="")
    # Estado de salud del proyecto (estilo Asana): se edita directo con
    # PATCH y también se sincroniza al crear un ProjectStatusUpdate.
    health = models.CharField(
        max_length=20, choices=Health.choices, null=True, blank=True,
        default=None,
    )
    # Favoritos por usuario (estrella Jira/Asana) para acceso rápido.
    favorited_by = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="favorite_projects",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name


def accessible_projects(user, write=False):
    """Proyectos accesibles por el usuario: propios + donde es miembro.

    Con ``write=True`` solo los que puede editar (owner o miembro
    con rol owner/editor). Los viewers solo tienen lectura.
    """
    qs = models.Q(owner=user)
    if write:
        qs |= models.Q(members__user=user, members__role__in=["owner", "editor"])
        # Org owner/admin → escritura en todos los proyectos de la org
        qs |= models.Q(
            organization__memberships__user=user,
            organization__memberships__role__in=["owner", "admin"],
        )
    else:
        qs |= models.Q(members__user=user)
        # Org member → lectura en proyectos de la org (guest sin acceso implícito)
        qs |= models.Q(
            organization__memberships__user=user,
            organization__memberships__role__in=["owner", "admin", "member"],
        )
    return Project.objects.filter(qs).distinct()


def derive_issue_prefix(name):
    """Deriva un prefijo de issue a partir del nombre del proyecto.

    Iniciales en mayúscula de cada palabra ("Mi Proyecto" → "MP"),
    clamp a 4 chars; si no hay iniciales aprovechables, primeros 3
    caracteres alfanuméricos del nombre en mayúscula.
    """
    words = [w for w in (name or "").split() if w]
    initials = "".join(w[0] for w in words if w[0].isalnum()).upper()
    if not initials:
        initials = "".join(c for c in (name or "") if c.isalnum()).upper()[:3]
    return initials[:4]


class ProjectSection(models.Model):
    """Sección dentro de un proyecto (columnas tipo Todoist/Asana).

    Las tareas pueden asignarse a una sección de su mismo proyecto
    (``Task.section``); al borrar la sección las tareas quedan sin
    sección (SET_NULL).
    """

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="sections"
    )
    name = models.CharField(max_length=120)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]
        unique_together = ("project", "name")

    def __str__(self):
        return f"{self.project}: {self.name}"


class ProjectStatusUpdate(models.Model):
    """Actualización de estado de un proyecto (histórico, estilo Asana).

    Cada update lleva un ``health`` que se copia al ``Project.health``
    actual al crearse. Los updates no se editan (inmutables como
    ``KeyResultUpdate``); solo su autor puede borrarlos.
    """

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="status_updates"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="project_status_updates",
    )
    health = models.CharField(
        max_length=20, choices=Project.Health.choices,
        default=Project.Health.ON_TRACK,
    )
    note = models.TextField(max_length=2000, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # -id como desempate: created_at puede repetirse en el mismo tick
        # del reloj (granularidad de datetime en Windows ~15ms) y el
        # "último" debe ser determinista.
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.project.name}: {self.health} @ {self.created_at:%Y-%m-%d}"


class ProjectRisk(models.Model):
    """Riesgo de proyecto: probabilidad × impacto con mitigación."""

    class Probability(models.TextChoices):
        LOW = "low", "Baja"
        MEDIUM = "medium", "Media"
        HIGH = "high", "Alta"

    class Impact(models.TextChoices):
        LOW = "low", "Bajo"
        MEDIUM = "medium", "Medio"
        HIGH = "high", "Alto"

    class Status(models.TextChoices):
        OPEN = "open", "Abierto"
        MITIGATED = "mitigated", "Mitigado"
        CLOSED = "closed", "Cerrado"
        REALIZED = "realized", "Materializado"

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="risks"
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    probability = models.CharField(
        max_length=10, choices=Probability.choices,
        default=Probability.MEDIUM,
    )
    impact = models.CharField(
        max_length=10, choices=Impact.choices, default=Impact.MEDIUM,
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.OPEN,
    )
    mitigation = models.TextField(blank=True, default="")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="risks",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["status", "-probability", "-impact"]

    def __str__(self):
        return f"{self.title} ({self.project.name})"

    @property
    def severity(self):
        """Severidad = probabilidad × impacto (low=1, medium=2, high=3)."""
        scale = {"low": 1, "medium": 2, "high": 3}
        return scale.get(self.probability, 0) * scale.get(self.impact, 0)


class Portfolio(models.Model):
    """Agrupación personal de proyectos (owner-scoped)."""

    name = models.CharField(max_length=120)
    color = models.CharField(max_length=7, default="#1976d2")  # hex
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="portfolios",
    )
    projects = models.ManyToManyField(
        Project, blank=True, related_name="portfolios"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class ProjectTemplate(models.Model):
    """Plantilla de proyecto: config JSON con tasks/tags/state_labels.

    ``is_builtin=True`` la hace visible para todos los usuarios (solo el
    owner puede editarla/borrarla igualmente). ``is_public=True`` la
    publica en el catálogo comunitario: cualquier usuario la ve y la
    aplica, pero solo el owner la edita/borra.
    """

    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, default="")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="project_templates",
    )
    config = models.JSONField(
        default=dict,
        help_text=(
            'Estructura: {"tasks": [{"title", "description", "priority", '
            '"task_type", "estimate_hours"}], "tags": [nombres], '
            '"state_labels": {state: label}}'
        ),
    )
    is_builtin = models.BooleanField(default=False)
    # Catálogo comunitario: publicada por el owner, visible para todos
    is_public = models.BooleanField(default=False)
    use_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class ProjectStateLabel(models.Model):
    """Etiqueta de display personalizada para un estado de Task en un proyecto.

    Solo renombra la etiqueta visible de los estados existentes de
    ``Task.State`` — no crea estados nuevos. La validación del valor de
    ``state`` se hace en el serializer (importar Task aquí crearía una
    dependencia circular: tasks ya importa projects).
    """

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="state_labels"
    )
    state = models.CharField(max_length=16)
    label = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("project", "state")
        ordering = ["state"]

    def __str__(self):
        return f"{self.project.name}: {self.state} → {self.label}"


class WorkflowTransition(models.Model):
    """Transición de estado permitida en un proyecto.

    Si un proyecto tiene AL MENOS una transición definida, los cambios de
    estado de sus tareas solo pueden seguir estas aristas (workflow
    configurable). Sin transiciones definidas el comportamiento es libre
    (backward compatible).
    """

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="workflow_transitions"
    )
    # Sin choices a nivel de modelo: el enum vive en tasks.Task.State y
    # importarlo aquí crearía una dependencia circular (tasks ya importa
    # projects). La validación se hace en el serializer/servicio.
    from_state = models.CharField(max_length=20)
    to_state = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("project", "from_state", "to_state")
        ordering = ["from_state", "to_state"]

    def __str__(self):
        return f"{self.project.name}: {self.from_state} → {self.to_state}"
