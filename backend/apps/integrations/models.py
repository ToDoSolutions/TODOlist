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
