"""Serializers para la API de integraciones."""
from rest_framework import serializers

from .models import (
    GitHubInstallation, GitHubRepo, GitHubIssueLink, WebhookDelivery,
    GitHubPullRequest, GitHubCommit, GitHubRelease, GitHubCheckRun,
)


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


class GitHubPullRequestSerializer(serializers.ModelSerializer):
    repo_full_name = serializers.CharField(source="repo.full_name", read_only=True)
    task_ids = serializers.PrimaryKeyRelatedField(
        many=True, read_only=True, source="tasks"
    )

    class Meta:
        model = GitHubPullRequest
        fields = [
            "id", "repo", "repo_full_name", "pr_number", "title", "state",
            "is_merged", "is_draft", "html_url", "head_branch", "base_branch",
            "author", "created_at_gh", "merged_at", "closed_at",
            "review_comments_count", "approvals_count", "changes_requested",
            "ci_status", "ci_url", "task_ids", "created_at", "updated_at",
        ]
        read_only_fields = fields


class GitHubCommitSerializer(serializers.ModelSerializer):
    repo_full_name = serializers.CharField(source="repo.full_name", read_only=True)
    task_ids = serializers.PrimaryKeyRelatedField(
        many=True, read_only=True, source="tasks"
    )

    class Meta:
        model = GitHubCommit
        fields = [
            "id", "repo", "repo_full_name", "sha", "message", "author",
            "author_date", "html_url", "task_ids", "created_at",
        ]
        read_only_fields = fields


class GitHubReleaseSerializer(serializers.ModelSerializer):
    repo_full_name = serializers.CharField(source="repo.full_name", read_only=True)
    task_ids = serializers.PrimaryKeyRelatedField(
        many=True, read_only=True, source="tasks"
    )
    pr_ids = serializers.PrimaryKeyRelatedField(
        many=True, read_only=True, source="pull_requests"
    )

    class Meta:
        model = GitHubRelease
        fields = [
            "id", "repo", "repo_full_name", "tag_name", "name", "body",
            "html_url", "state", "is_prerelease", "author", "published_at",
            "task_ids", "pr_ids", "created_at", "updated_at",
        ]
        read_only_fields = fields


class GitHubCheckRunSerializer(serializers.ModelSerializer):
    repo_full_name = serializers.CharField(source="repo.full_name", read_only=True)

    class Meta:
        model = GitHubCheckRun
        fields = [
            "id", "repo", "repo_full_name", "check_id", "name", "status",
            "conclusion", "html_url", "started_at", "completed_at",
            "commit_sha", "pull_request", "created_at",
        ]
        read_only_fields = fields
