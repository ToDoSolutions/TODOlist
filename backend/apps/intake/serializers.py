from rest_framework import serializers

from .models import IntakeForm, IntakeSubmission


class IntakeFormSerializer(serializers.ModelSerializer):
    submissions_count = serializers.SerializerMethodField()

    class Meta:
        model = IntakeForm
        fields = [
            "id", "project", "name", "description", "schema",
            "task_defaults", "enabled", "public_token",
            "submissions_count",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "public_token", "created_at", "updated_at",
        ]

    def get_submissions_count(self, obj):
        # Usa la anotación del queryset si existe (evita N+1 en list)
        ann = getattr(obj, "submissions_count_ann", None)
        return ann if ann is not None else obj.submissions.count()

    def validate_schema(self, value):
        form = IntakeForm(schema=value)
        errors = form.validate_schema()
        if errors:
            raise serializers.ValidationError(errors)
        return value


class IntakeSubmissionSerializer(serializers.ModelSerializer):
    task_id = serializers.IntegerField(read_only=True)
    submitted_by_email = serializers.CharField(
        source="submitted_by.email", read_only=True
    )
    task_title = serializers.SerializerMethodField()

    class Meta:
        model = IntakeSubmission
        fields = [
            "id", "form", "data", "task_id", "task_title",
            "submitted_by_email", "created_at",
        ]
        read_only_fields = ["id", "task_id", "created_at"]

    def get_task_title(self, obj):
        return obj.task.title if obj.task else None
