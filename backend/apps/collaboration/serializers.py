"""Serializers para colaboración."""
from django.conf import settings
from rest_framework import serializers

from .models import (
    AuditLog,
    ExternalCalendar,
    ExternalEvent,
    Invitation,
    Meeting,
    Mention,
    ProjectMember,
    Team,
    TeamMembership,
    Whiteboard,
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
    user_display = serializers.SerializerMethodField()
    user_out_of_office = serializers.BooleanField(
        source="user.out_of_office", read_only=True
    )
    user_out_of_office_until = serializers.DateField(
        source="user.out_of_office_until", read_only=True
    )

    class Meta:
        model = ProjectMember
        fields = [
            "id", "project", "user", "user_email", "user_username", "user_display",
            "user_out_of_office", "user_out_of_office_until",
            "role", "invited_by", "joined_at",
        ]
        read_only_fields = [
            "id", "invited_by", "joined_at", "user_email", "user_username",
            "user_display", "user_out_of_office", "user_out_of_office_until",
        ]

    def get_user_display(self, obj):
        return obj.user.email if obj.user else ""


class InvitationSerializer(serializers.ModelSerializer):
    invited_by_email = serializers.CharField(
        source="invited_by.email", read_only=True
    )
    target_name = serializers.SerializerMethodField()

    class Meta:
        model = Invitation
        fields = [
            "id", "target_type", "target_id", "target_name", "email", "role",
            "invited_by", "invited_by_email", "status", "created_at",
            "expires_at", "responded_at",
        ]
        read_only_fields = [
            "id", "invited_by", "invited_by_email", "target_name", "status",
            "created_at", "expires_at", "responded_at",
        ]

    def get_target_name(self, obj):
        if obj.target_type == Invitation.TargetType.TEAM:
            return Team.objects.filter(pk=obj.target_id).values_list(
                "name", flat=True).first() or ""
        from apps.tasks.models import Project
        return Project.objects.filter(pk=obj.target_id).values_list(
            "name", flat=True).first() or ""


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


class MeetingSerializer(serializers.ModelSerializer):
    tasks_ids: serializers.Field = serializers.PrimaryKeyRelatedField(
        many=True, read_only=True, source="tasks"
    )
    attendees_emails = serializers.SerializerMethodField()
    video_url = serializers.SerializerMethodField()

    class Meta:
        model = Meeting
        fields = [
            "id", "title", "project", "scheduled_at",
            "duration_minutes", "attendees", "attendees_emails",
            "notes", "decisions", "tasks_ids",
            "video_room", "video_url",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "video_url", "created_at", "updated_at"]

    def get_attendees_emails(self, obj):
        return [a.email for a in obj.attendees.all()]

    def get_video_url(self, obj):
        """URL completa de la sala Jitsi, o null si no hay sala creada."""
        if not obj.video_room:
            return None
        base = settings.JITSI_BASE_URL.rstrip("/")
        return f"{base}/{obj.video_room}"


class OrganizationSerializer(serializers.ModelSerializer):
    member_count = serializers.IntegerField(source="memberships.count", read_only=True)

    class Meta:
        from .models import Organization
        model = Organization
        fields = [
            "id", "name", "slug", "description", "owner",
            "member_count", "sso_domain", "sso_required", "created_at",
        ]
        read_only_fields = ["id", "slug", "owner", "created_at"]

    def validate_sso_domain(self, value):
        """Normaliza el dominio reclamado ('@acme.com' → 'acme.com') y
        garantiza unicidad entre orgs — dos orgs no pueden reclamar el
        mismo dominio SSO."""
        value = (value or "").strip().lower().lstrip("@")
        if not value:
            return None
        from .models import Organization
        qs = Organization.objects.filter(sso_domain__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "Ese dominio ya está reclamado por otra organización."
            )
        return value


class OrganizationMembershipSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        from .models import OrganizationMembership
        model = OrganizationMembership
        fields = ["id", "organization", "user", "user_email", "role", "created_at"]
        read_only_fields = ["id", "user_email", "created_at"]


class ExternalCalendarSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExternalCalendar
        fields = [
            "id", "name", "url", "color", "is_active",
            "last_synced_at", "last_error", "created_at",
        ]
        read_only_fields = ["id", "last_synced_at", "last_error", "created_at"]


class ExternalEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExternalEvent
        fields = ["id", "uid", "summary", "dtstart", "dtend", "all_day"]
        read_only_fields = fields


class WhiteboardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Whiteboard
        fields = [
            "id", "project", "name", "owner", "content",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "owner", "created_at", "updated_at"]
