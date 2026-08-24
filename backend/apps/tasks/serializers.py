from rest_framework import serializers

from apps.projects.models import Project
from apps.tags.models import Tag

from .models import (
    Task, Subtask, Comment, RecurrenceRule, TaskRelation, TaskActivity,
    Sprint, Epic, SavedSearch, TimeEntry, Attachment, TaskTemplate,
    CustomField, CustomFieldValue, OutgoingWebhook,
)


class RecurrenceRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecurrenceRule
        fields = [
            "id", "frequency", "interval", "until", "count",
            "occurrences_generated", "created_at",
        ]
        read_only_fields = ["id", "occurrences_generated", "created_at"]


class SubtaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subtask
        fields = ["id", "title", "is_done", "order", "created_at"]
        read_only_fields = ["id", "created_at"]


class CommentSerializer(serializers.ModelSerializer):
    author_email = serializers.CharField(source="author.email", read_only=True)

    class Meta:
        model = Comment
        fields = ["id", "body", "author_email", "created_at", "updated_at"]
        read_only_fields = ["id", "author_email", "created_at", "updated_at"]


class TaskRelationSerializer(serializers.ModelSerializer):
    source_title = serializers.CharField(source="source.title", read_only=True)
    target_title = serializers.CharField(source="target.title", read_only=True)

    class Meta:
        model = TaskRelation
        fields = ["id", "source", "source_title", "target", "target_title",
                  "relation_type", "created_at"]
        read_only_fields = ["id", "source", "source_title", "target_title", "created_at"]


class TaskActivitySerializer(serializers.ModelSerializer):
    actor_email = serializers.CharField(source="actor.email", read_only=True)

    class Meta:
        model = TaskActivity
        fields = ["id", "actor", "actor_email", "action", "field",
                  "old_value", "new_value", "created_at"]
        read_only_fields = fields


class SprintSerializer(serializers.ModelSerializer):
    task_count = serializers.SerializerMethodField()

    class Meta:
        model = Sprint
        fields = ["id", "name", "goal", "description", "state",
                  "start_date", "end_date", "project", "task_count",
                  "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_task_count(self, obj):
        return obj.tasks.count()


class EpicSerializer(serializers.ModelSerializer):
    progress_done = serializers.SerializerMethodField()
    progress_total = serializers.SerializerMethodField()

    class Meta:
        model = Epic
        fields = ["id", "title", "description", "state", "color",
                  "start_date", "end_date", "project",
                  "progress_done", "progress_total",
                  "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_progress_done(self, obj):
        return obj.progress[0]

    def get_progress_total(self, obj):
        return obj.progress[1]


class SavedSearchSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedSearch
        fields = ["id", "name", "filters", "is_shared",
                  "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class TaskSerializer(serializers.ModelSerializer):
    subtasks = SubtaskSerializer(many=True, read_only=True)
    comments = CommentSerializer(many=True, read_only=True)
    tags_ids = serializers.PrimaryKeyRelatedField(
        many=True, read_only=True, source="tags"
    )
    recurrence = RecurrenceRuleSerializer(read_only=True)
    relations = TaskRelationSerializer(source="outgoing_relations", many=True, read_only=True)
    activities = TaskActivitySerializer(many=True, read_only=True)
    subtask_done = serializers.SerializerMethodField()
    subtask_total = serializers.SerializerMethodField()
    sprint_name = serializers.CharField(source="sprint.name", read_only=True)
    epic_title = serializers.CharField(source="epic.title", read_only=True)
    parent_title = serializers.CharField(source="parent.title", read_only=True)

    class Meta:
        model = Task
        fields = [
            "id", "title", "description", "state", "priority", "task_type",
            "due_date", "start_date", "completed_at",
            "story_points", "estimate_hours", "size",
            "project", "tags", "tags_ids",
            "recurrence",
            "parent", "parent_title",
            "sprint", "sprint_name",
            "epic", "epic_title",
            "relations", "activities",
            "subtask_done", "subtask_total",
            "subtasks", "comments",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "completed_at", "created_at", "updated_at"]

    def get_subtask_done(self, obj):
        return obj.subtask_progress[0]

    def get_subtask_total(self, obj):
        return obj.subtask_progress[1]


class TaskCreateUpdateSerializer(serializers.ModelSerializer):
    tags = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Tag.objects.none(), required=False
    )
    recurrence_data = RecurrenceRuleSerializer(write_only=True, required=False)

    class Meta:
        model = Task
        fields = [
            "id", "title", "description", "state", "priority", "task_type",
            "due_date", "start_date",
            "story_points", "estimate_hours", "size",
            "project", "tags", "recurrence_data",
            "parent", "sprint", "epic",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            self.fields["tags"].child_relation.queryset = Tag.objects.filter(
                owner=request.user
            )

    def validate_project(self, value):
        if value is None:
            return value
        request = self.context.get("request")
        if request and not Project.objects.filter(id=value.id, owner=request.user).exists():
            raise serializers.ValidationError("El proyecto no existe o no te pertenece.")
        return value

    def validate_parent(self, value):
        """Evita ciclos jerarquicos."""
        if value is None:
            return value
        request = self.context.get("request")
        if request and not Task.objects.filter(id=value.id, owner=request.user).exists():
            raise serializers.ValidationError("La tarea padre no existe o no te pertenece.")
        # Evitar auto-referencia
        if self.instance and value.id == self.instance.id:
            raise serializers.ValidationError("Una tarea no puede ser su propia padre.")
        # Evitar ciclos: subir por la cadena de padres
        if self.instance:
            parent = value
            while parent:
                if parent.id == self.instance.id:
                    raise serializers.ValidationError("Ciclo detectado en la jerarquia.")
                parent = parent.parent
        return value

    def create(self, validated_data):
        tags = validated_data.pop("tags", [])
        recurrence_data = validated_data.pop("recurrence_data", None)
        if recurrence_data:
            recurrence = RecurrenceRule.objects.create(**recurrence_data)
            validated_data["recurrence"] = recurrence
        task = Task.objects.create(**validated_data)
        if tags:
            task.tags.set(tags)
        # Registrar actividad
        TaskActivity.objects.create(
            task=task,
            actor=task.owner,
            action=TaskActivity.ActionType.CREATED,
        )
        return task


class TimeEntrySerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        model = TimeEntry
        fields = [
            "id", "task", "user", "user_email", "duration_seconds",
            "description", "started_at", "ended_at", "created_at",
        ]
        read_only_fields = ["id", "user", "user_email", "created_at"]


class AttachmentSerializer(serializers.ModelSerializer):
    uploaded_by_email = serializers.CharField(source="uploaded_by.email", read_only=True)

    class Meta:
        model = Attachment
        fields = [
            "id", "task", "comment", "uploaded_by", "uploaded_by_email",
            "file", "filename", "file_size", "content_type", "created_at",
        ]
        read_only_fields = ["id", "uploaded_by", "uploaded_by_email", "file_size", "content_type", "created_at"]


class TaskTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskTemplate
        fields = [
            "id", "name", "description", "owner", "project",
            "template_data", "created_at",
        ]
        read_only_fields = ["id", "owner", "created_at"]


class CustomFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomField
        fields = [
            "id", "project", "name", "field_type", "options",
            "is_required", "default_value", "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class CustomFieldValueSerializer(serializers.ModelSerializer):
    field_name = serializers.CharField(source="field.name", read_only=True)

    class Meta:
        model = CustomFieldValue
        fields = ["id", "task", "field", "field_name", "value", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at", "field_name"]


class OutgoingWebhookSerializer(serializers.ModelSerializer):
    class Meta:
        model = OutgoingWebhook
        fields = [
            "id", "owner", "url", "events", "secret",
            "is_active", "created_at",
        ]
        read_only_fields = ["id", "owner", "created_at"]

    def update(self, instance, validated_data):
        tags = validated_data.pop("tags", None)
        recurrence_data = validated_data.pop("recurrence_data", None)
        if recurrence_data:
            if instance.recurrence:
                for k, v in recurrence_data.items():
                    setattr(instance.recurrence, k, v)
                instance.recurrence.save()
            else:
                instance.recurrence = RecurrenceRule.objects.create(**recurrence_data)

        # Registrar cambios de campos importantes
        request = self.context.get("request")
        actor = request.user if request else instance.owner
        for field in ["state", "priority", "sprint", "parent"]:
            if field in validated_data:
                old = getattr(instance, field, None)
                new = validated_data[field]
                if old != new:
                    action_map = {
                        "state": TaskActivity.ActionType.STATE_CHANGED,
                        "priority": TaskActivity.ActionType.PRIORITY_CHANGED,
                        "sprint": TaskActivity.ActionType.SPRINT_CHANGED,
                    }
                    TaskActivity.objects.create(
                        task=instance,
                        actor=actor,
                        action=action_map.get(field, TaskActivity.ActionType.UPDATED),
                        field=field,
                        old_value=str(old) if old else "",
                        new_value=str(new) if new else "",
                    )

        for k, v in validated_data.items():
            setattr(instance, k, v)
        instance.save()
        if tags is not None:
            instance.tags.set(tags)
        return instance
