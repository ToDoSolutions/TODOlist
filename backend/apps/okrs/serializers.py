from rest_framework import serializers

from apps.okrs.models import KeyResult, KeyResultUpdate, Objective
from apps.tasks.models import Task


class KeyResultUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = KeyResultUpdate
        fields = [
            "id",
            "key_result",
            "user",
            "old_value",
            "new_value",
            "note",
            "created_at",
        ]
        read_only_fields = ["user", "old_value", "created_at"]

    def validate_key_result(self, value):
        request = self.context.get("request")
        if request and value.owner_id != request.user.id:
            raise serializers.ValidationError("El Key Result no existe o no te pertenece.")
        return value


class KeyResultSerializer(serializers.ModelSerializer):
    updates = KeyResultUpdateSerializer(many=True, read_only=True)
    # Escritura: lista de ids de Task; lectura: los ids vía linked_tasks.
    linked_tasks = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Task.objects.all(), required=False
    )
    linked_tasks_detail = serializers.SerializerMethodField()
    linked_progress = serializers.SerializerMethodField()

    class Meta:
        model = KeyResult
        fields = [
            "id",
            "objective",
            "title",
            "target_value",
            "current_value",
            "unit",
            "owner",
            "due_date",
            "linked_tasks",
            "linked_tasks_detail",
            "linked_progress",
            "created_at",
            "updates",
        ]
        read_only_fields = ["owner", "current_value", "created_at"]

    def validate_objective(self, value):
        request = self.context.get("request")
        if request and value.owner_id != request.user.id:
            raise serializers.ValidationError("El objetivo no existe o no te pertenece.")
        return value

    def validate_linked_tasks(self, value):
        """Cada tarea vinculada debe ser visible para el usuario."""
        request = self.context.get("request")
        if request and value:
            visible = set(
                Task.objects.for_user(request.user)
                .filter(id__in=[t.id for t in value])
                .values_list("id", flat=True)
            )
            foreign = [t.id for t in value if t.id not in visible]
            if foreign:
                raise serializers.ValidationError(
                    f"Tareas inexistentes o sin acceso: {foreign}"
                )
        return value

    def get_linked_tasks_detail(self, obj):
        return [
            {"id": t.id, "title": t.title, "state": t.state}
            for t in obj.linked_tasks.all()
        ]

    def get_linked_progress(self, obj):
        """% (0-100) de tareas vinculadas con state == completed."""
        tasks = list(obj.linked_tasks.all())
        if not tasks:
            return 0
        done = sum(1 for t in tasks if t.state == "completed")
        return round(done / len(tasks) * 100)


class ObjectiveSerializer(serializers.ModelSerializer):
    key_results = KeyResultSerializer(many=True, read_only=True)

    class Meta:
        model = Objective
        fields = [
            "id",
            "owner",
            "title",
            "description",
            "quarter",
            "year",
            "status",
            "progress",
            "created_at",
            "updated_at",
            "key_results",
        ]
        read_only_fields = ["owner", "progress", "created_at", "updated_at"]
