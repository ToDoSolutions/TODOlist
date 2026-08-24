"""Modelos para integración con GitHub."""
from django.conf import settings
from django.db import models


class WebhookDelivery(models.Model):
    """Registra cada entrega de webhook para idempotencia y reintentos.

    GitHub envía un ID de entrega (X-GitHub-Delivery) que es único
    por evento. Lo usamos para evitar procesar el mismo evento dos veces.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        PROCESSED = "processed", "Procesado"
        FAILED = "failed", "Fallido"
        RETRYING = "retrying", "Reintentando"
        DEAD_LETTER = "dead_letter", "Cola de mensajes fallidos"

    delivery_id = models.CharField(max_length=100, unique=True, db_index=True)
    event_type = models.CharField(max_length=50)
    action = models.CharField(max_length=50, blank=True, default="")
    payload = models.JSONField(default=dict)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    error_message = models.TextField(blank=True, default="")
    retry_count = models.PositiveIntegerField(default=0)
    max_retries = models.PositiveIntegerField(default=5)
    repo_full_name = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    next_retry_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["next_retry_at"]),
        ]

    def __str__(self):
        return f"{self.delivery_id} ({self.event_type}/{self.action}) = {self.status}"

    @property
    def is_dead(self):
        return self.status == self.Status.DEAD_LETTER

    @property
    def can_retry(self):
        return self.retry_count < self.max_retries and not self.is_dead


class GitHubInstallation(models.Model):
    """Instalación de la GitHub App para un usuario.
    Se crea tras el flujo OAuth o cuando la App se instala en una org.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="github_installations",
    )
    installation_id = models.BigIntegerField(unique=True)
    account_login = models.CharField(max_length=255)  # usuario u org de GitHub
    account_type = models.CharField(max_length=50, default="User")  # User u Organization
    avatar_url = models.URLField(max_length=500, blank=True, default="")

    # Token OAuth del usuario (para login con GitHub y API calls como usuario)
    github_user_id = models.BigIntegerField(null=True, blank=True)
    github_username = models.CharField(max_length=255, blank=True, default="")
    access_token = models.TextField(blank=True, default="")  # OAuth token
    refresh_token = models.TextField(blank=True, default="")
    token_expires_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.account_login} (installation {self.installation_id})"


class GitHubRepo(models.Model):
    """Repositorio seleccionado por el usuario para sincronizar."""

    installation = models.ForeignKey(
        GitHubInstallation,
        on_delete=models.CASCADE,
        related_name="repos",
    )
    repo_id = models.BigIntegerField()
    full_name = models.CharField(max_length=255)  # owner/repo
    name = models.CharField(max_length=255)
    owner = models.CharField(max_length=255)
    is_private = models.BooleanField(default=False)
    sync_enabled = models.BooleanField(default=True)
    default_branch = models.CharField(max_length=255, default="main")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("installation", "repo_id")
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name


class GitHubIssueLink(models.Model):
    """Relación bidireccional entre una tarea local y un issue de GitHub."""

    task = models.OneToOneField(
        "tasks.Task",
        on_delete=models.CASCADE,
        related_name="github_link",
    )
    repo = models.ForeignKey(
        GitHubRepo,
        on_delete=models.CASCADE,
        related_name="issue_links",
    )
    issue_number = models.IntegerField()
    issue_id = models.BigIntegerField()  # ID global del issue en GitHub
    issue_url = models.URLField(max_length=500)
    issue_state = models.CharField(max_length=20, default="open")  # open/closed
    last_synced_at = models.DateTimeField(null=True, blank=True)

    # Para GitHub Projects v2
    project_node_id = models.CharField(max_length=100, blank=True, default="")
    project_status = models.CharField(max_length=50, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("repo", "issue_number")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.repo.full_name}#{self.issue_number} ↔ {self.task.title}"


class GitHubPullRequest(models.Model):
    """Pull request de GitHub vinculado a tareas para trazabilidad."""

    repo = models.ForeignKey(
        GitHubRepo, on_delete=models.CASCADE, related_name="pull_requests"
    )
    pr_number = models.IntegerField()
    pr_id = models.BigIntegerField()
    title = models.CharField(max_length=500)
    state = models.CharField(max_length=20, default="open")  # open/closed
    is_merged = models.BooleanField(default=False)
    is_draft = models.BooleanField(default=False)
    html_url = models.URLField(max_length=500)
    head_branch = models.CharField(max_length=255, blank=True, default="")
    base_branch = models.CharField(max_length=255, blank=True, default="")
    author = models.CharField(max_length=255, blank=True, default="")
    # Tiempos para métricas
    created_at_gh = models.DateTimeField(null=True, blank=True)
    merged_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    # Review
    review_comments_count = models.IntegerField(default=0)
    approvals_count = models.IntegerField(default=0)
    changes_requested = models.BooleanField(default=False)
    # CI
    ci_status = models.CharField(max_length=50, blank=True, default="")  # success/failure/pending
    ci_url = models.URLField(max_length=500, blank=True, default="")

    tasks = models.ManyToManyField(
        "tasks.Task", blank=True, related_name="pull_requests"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("repo", "pr_number")
        ordering = ["-created_at_gh"]

    def __str__(self):
        return f"{self.repo.full_name}#{self.pr_number} ({self.state})"


class GitHubCommit(models.Model):
    """Commit de GitHub referenciado por una tarea."""

    repo = models.ForeignKey(
        GitHubRepo, on_delete=models.CASCADE, related_name="commits"
    )
    sha = models.CharField(max_length=40, unique=True)
    message = models.TextField()
    author = models.CharField(max_length=255, blank=True, default="")
    author_date = models.DateTimeField(null=True, blank=True)
    html_url = models.URLField(max_length=500, blank=True, default="")
    # Tareas referenciadas (detectadas por #issue_number en el mensaje)
    tasks = models.ManyToManyField(
        "tasks.Task", blank=True, related_name="commits"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-author_date"]

    def __str__(self):
        return f"{self.sha[:8]} ({self.repo.full_name})"


class GitHubRelease(models.Model):
    """Release de GitHub para rastrear versiones y trabajo asociado."""

    class ReleaseState(models.TextChoices):
        DRAFT = "draft", "Borrador"
        PUBLISHED = "published", "Publicada"
        PRERELEASE = "prerelease", "Pre-release"

    repo = models.ForeignKey(
        GitHubRepo, on_delete=models.CASCADE, related_name="releases"
    )
    release_id = models.BigIntegerField(unique=True)
    tag_name = models.CharField(max_length=255)
    name = models.CharField(max_length=500, blank=True, default="")
    body = models.TextField(blank=True, default="")
    html_url = models.URLField(max_length=500)
    state = models.CharField(
        max_length=20, choices=ReleaseState.choices, default=ReleaseState.PUBLISHED
    )
    is_prerelease = models.BooleanField(default=False)
    author = models.CharField(max_length=255, blank=True, default="")
    published_at = models.DateTimeField(null=True, blank=True)
    # Tareas y PRs asociados
    tasks = models.ManyToManyField(
        "tasks.Task", blank=True, related_name="releases"
    )
    pull_requests = models.ManyToManyField(
        GitHubPullRequest, blank=True, related_name="releases"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-published_at"]

    def __str__(self):
        return f"{self.repo.full_name} {self.tag_name}"


class GitHubCheckRun(models.Model):
    """Estado de CI/CD (GitHub Actions checks) asociado a un PR o commit."""

    class CheckStatus(models.TextChoices):
        QUEUED = "queued", "En cola"
        IN_PROGRESS = "in_progress", "En progreso"
        COMPLETED = "completed", "Completado"

    class CheckConclusion(models.TextChoices):
        SUCCESS = "success", "Éxito"
        FAILURE = "failure", "Fallo"
        NEUTRAL = "neutral", "Neutral"
        CANCELLED = "cancelled", "Cancelado"
        SKIPPED = "skipped", "Omitido"
        TIMED_OUT = "timed_out", "Tiempo agotado"

    repo = models.ForeignKey(
        GitHubRepo, on_delete=models.CASCADE, related_name="check_runs"
    )
    check_id = models.BigIntegerField(unique=True)
    name = models.CharField(max_length=255)  # nombre del workflow
    status = models.CharField(
        max_length=20, choices=CheckStatus.choices, default=CheckStatus.QUEUED
    )
    conclusion = models.CharField(
        max_length=20, choices=CheckConclusion.choices, blank=True, default=""
    )
    html_url = models.URLField(max_length=500, blank=True, default="")
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    # Commit asociado
    commit_sha = models.CharField(max_length=40, blank=True, default="")
    # PR asociado (opcional)
    pull_request = models.ForeignKey(
        GitHubPullRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="check_runs",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.name} ({self.status}/{self.conclusion or '—'})"
