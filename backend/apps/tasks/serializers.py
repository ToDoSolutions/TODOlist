from rest_framework import serializers

from apps.tags.models import Tag

from .models import Task, Subtask, Comment


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

    class Meta:
        model = Task
        fields = [
            "id", "title", "description", "state", "priority",
            "due_date", "completed_at",
            "project", "tags", "tags_ids",
            "subtasks", "comments",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "completed_at", "created_at", "updated_at"]


class TaskCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer para crear/actualizar: acepta IDs de etiquetas."""

    tags = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Tag.objects.none(), required=False
    )

    class Meta:
        model = Task
        fields = [
            "id", "title", "description", "state", "priority",
            "due_date", "project", "tags",
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
