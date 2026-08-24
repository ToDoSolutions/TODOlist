from rest_framework import serializers

from apps.projects.models import Project
from apps.tags.models import Tag

from .models import Task, Subtask, Comment, RecurrenceRule


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


class TaskSerializer(serializers.ModelSerializer):
    subtasks = SubtaskSerializer(many=True, read_only=True)
    comments = CommentSerializer(many=True, read_only=True)
    tags_ids = serializers.PrimaryKeyRelatedField(
        many=True, read_only=True, source="tags"
    )
    recurrence = RecurrenceRuleSerializer(read_only=True)

    class Meta:
        model = Task
        fields = [
            "id", "title", "description", "state", "priority",
            "due_date", "completed_at",
            "project", "tags", "tags_ids",
            "recurrence",
            "subtasks", "comments",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "completed_at", "created_at", "updated_at"]


class TaskCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer para crear/actualizar: acepta IDs de etiquetas y recurrencia."""

    tags = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Tag.objects.none(), required=False
    )
    recurrence_data = RecurrenceRuleSerializer(write_only=True, required=False)

    class Meta:
        model = Task
        fields = [
            "id", "title", "description", "state", "priority",
            "due_date", "project", "tags", "recurrence_data",
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

    def create(self, validated_data):
        tags = validated_data.pop("tags", [])
        recurrence_data = validated_data.pop("recurrence_data", None)
        if recurrence_data:
            recurrence = RecurrenceRule.objects.create(**recurrence_data)
            validated_data["recurrence"] = recurrence
        task = Task.objects.create(**validated_data)
        if tags:
            task.tags.set(tags)
        return task

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
        for k, v in validated_data.items():
            setattr(instance, k, v)
        instance.save()
        if tags is not None:
            instance.tags.set(tags)
        return instance
