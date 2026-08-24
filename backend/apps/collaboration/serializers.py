"""Serializers para colaboración."""
from rest_framework import serializers
from .models import (
    Team, TeamMembership, ProjectMember, Invitation, Mention, AuditLog,
)


class TeamMembershipSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True)
    user_username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = TeamMembership
        fields = [
            "id", "team", "user", "user_email", "user_username",
            "role", "joined_at",
        ]
        read_only_fields = ["id", "joined_at", "user_email", "user_username"]


class TeamSerializer(serializers.ModelSerializer):
    member_count = serializers.IntegerField(source="memberships.count", read_only=True)

    class Meta:
        model = Team
        fields = [
            "id", "name", "slug", "description", "owner",
            "member_count", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "slug", "owner", "created_at", "updated_at"]


class ProjectMemberSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True)
    user_username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = ProjectMember
        fields = [
            "id", "project", "user", "user_email", "user_username",
            "role", "invited_by", "joined_at",
        ]
        read_only_fields = ["id", "invited_by", "joined_at", "user_email", "user_username"]


class InvitationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invitation
        fields = [
            "id", "target_type", "target_id", "email", "role",
            "invited_by", "token", "status", "created_at", "responded_at",
        ]
        read_only_fields = ["id", "invited_by", "token", "status", "created_at", "responded_at"]


class MentionSerializer(serializers.ModelSerializer):
    mentioned_by_email = serializers.CharField(source="mentioned_by.email", read_only=True)
    mentioned_user_email = serializers.CharField(source="mentioned_user.email", read_only=True)

    class Meta:
        model = Mention
        fields = [
            "id", "comment", "task", "mentioned_user", "mentioned_user_email",
            "mentioned_by", "mentioned_by_email", "created_at",
        ]
        read_only_fields = fields


class AuditLogSerializer(serializers.ModelSerializer):
    actor_email = serializers.CharField(source="actor.email", read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            "id", "actor", "actor_email", "action",
            "resource_type", "resource_id", "resource_name",
            "old_values", "new_values",
            "ip_address", "user_agent", "created_at",
        ]
        read_only_fields = fields
