from datetime import timedelta

from django.utils import timezone
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

    def validate(self, data):
        target = data.get("target")
        if not target:
            raise serializers.ValidationError("Debes especificar una tarea objetivo.")
        # source se settea en la view, pero si existe validamos
        source = data.get("source", getattr(self.instance, "source", None))
        if source and target and source.id == target.id:
            raise serializers.ValidationError("Una tarea no puede relacionarse consigo misma.")
        # Evitar dependencia circular: si A blocks B, B no puede blocks A
        relation_type = data.get("relation_type", getattr(self.instance, "relation_type", None))
        if source and target and relation_type in ("blocks", "depends_on"):
            reverse_type = "depends_on" if relation_type == "blocks" else "blocks"
            if TaskRelation.objects.filter(
                source=target, target=source, relation_type=reverse_type
            ).exists():
                raise serializers.ValidationError(
                    "Dependencia circular: la tarea objetivo ya bloquea a la tarea origen."
                )
        return data


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

    def validate(self, data):
        start = data.get("start_date", getattr(self.instance, "start_date", None))
        end = data.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end < start:
            raise serializers.ValidationError(
                "La fecha de fin del sprint debe ser posterior a la de inicio."
            )
        # Solo un sprint activo por proyecto
        state = data.get("state", getattr(self.instance, "state", None))
        project = data.get("project", getattr(self.instance, "project", None))
        if state == "active" and project:
            qs = Sprint.objects.filter(project=project, state="active")
            if self.instance:
                qs = qs.exclude(id=self.instance.id)
            if qs.exists():
                raise serializers.ValidationError(
                    "Ya existe un sprint activo para este proyecto."
                )
        return data


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

    def validate(self, data):
        start = data.get("start_date", getattr(self.instance, "start_date", None))
        end = data.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end < start:
            raise serializers.ValidationError(
                "La fecha de fin de la épica debe ser posterior a la de inicio."
            )
        return data


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

    def validate_priority(self, value):
        if value is not None and (value < 0 or value > 5):
            raise serializers.ValidationError("La prioridad debe estar entre 0 y 5.")
        return value

    def validate_story_points(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("Los story points no pueden ser negativos.")
        return value

    def validate(self, data):
        # Sprint y epic deben pertenecer al mismo proyecto
        sprint = data.get("sprint", getattr(self.instance, "sprint", None))
        epic = data.get("epic", getattr(self.instance, "epic", None))
        project = data.get("project", getattr(self.instance, "project", None))
        if sprint and project and sprint.project_id and sprint.project_id != project.id:
            raise serializers.ValidationError(
                "El sprint debe pertenecer al mismo proyecto que la tarea."
            )
        if epic and project and epic.project_id and epic.project_id != project.id:
            raise serializers.ValidationError(
                "La épica debe pertenecer al mismo proyecto que la tarea."
            )
        # No permitir due_date en el pasado para tareas nuevas
        due_date = data.get("due_date")
        if due_date and not self.instance:
            today = timezone.now().date()
            if hasattr(due_date, "date"):
                d = due_date.date()
            else:
                d = due_date
            if d < today:
                raise serializers.ValidationError(
                    "No puedes crear una tarea con fecha de vencimiento en el pasado."
                )
        return data

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

    def validate_task(self, value):
        if value is None:
            raise serializers.ValidationError("Debes asociar el registro de tiempo a una tarea.")
        return value

    def validate_duration_seconds(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError("La duración debe ser mayor que cero.")
        return value

    def validate_started_at(self, value):
        if value and not self.instance:
            today = timezone.now()
            if hasattr(value, "tzinfo") and value.tzinfo is None:
                value = timezone.make_aware(value)
            if value > today + timedelta(minutes=5):
                raise serializers.ValidationError(
                    "No puedes registrar tiempo en el futuro."
                )
        return value


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
