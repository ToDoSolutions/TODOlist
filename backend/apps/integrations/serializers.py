"""Serializers para la API de integraciones."""
from rest_framework import serializers

from .models import GitHubInstallation, GitHubRepo, GitHubIssueLink, WebhookDelivery


class GitHubInstallationSerializer(serializers.ModelSerializer):
    class Meta:
        model = GitHubInstallation
        fields = [
            "id", "installation_id", "account_login", "account_type",
            "avatar_url", "github_username", "created_at",
        ]
        read_only_fields = fields


class GitHubRepoSerializer(serializers.ModelSerializer):
    installation = GitHubInstallationSerializer(read_only=True)

    class Meta:
        model = GitHubRepo
        fields = [
            "id", "installation", "repo_id", "full_name", "name", "owner",
            "is_private", "sync_enabled", "default_branch", "created_at",
        ]
        read_only_fields = [
            "id", "installation", "repo_id", "full_name", "name", "owner",
            "is_private", "default_branch", "created_at",
        ]


class GitHubIssueLinkSerializer(serializers.ModelSerializer):
    repo_full_name = serializers.CharField(source="repo.full_name", read_only=True)

    class Meta:
        model = GitHubIssueLink
        fields = [
            "id", "task", "repo", "repo_full_name", "issue_number",
            "issue_url", "issue_state", "last_synced_at", "created_at",
        ]
        read_only_fields = fields


class ImportIssuesSerializer(serializers.Serializer):
    """Serializer para importar issues desde un repo."""
    state = serializers.ChoiceField(
        choices=["open", "closed", "all"], default="open"
    )
    label_filter = serializers.CharField(required=False, allow_blank=True)


class CreateIssueSerializer(serializers.Serializer):
    """Serializer para crear un issue desde una tarea existente."""
    task_id = serializers.IntegerField()
    repo_id = serializers.IntegerField()


class WebhookDeliverySerializer(serializers.ModelSerializer):
    """Serializer para auditoría de entregas de webhooks."""

    class Meta:
        model = WebhookDelivery
        fields = [
            "id", "delivery_id", "event_type", "action", "status",
            "error_message", "retry_count", "max_retries",
            "repo_full_name", "created_at", "processed_at", "next_retry_at",
        ]
        read_only_fields = fields
