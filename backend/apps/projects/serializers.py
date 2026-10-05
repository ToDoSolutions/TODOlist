from rest_framework import serializers

from .models import Project, ProjectRisk, ProjectStatusUpdate


class ProjectSerializer(serializers.ModelSerializer):
    tasks_count = serializers.SerializerMethodField()
    sprints_count = serializers.SerializerMethodField()
    epics_count = serializers.SerializerMethodField()
    completed_tasks_count = serializers.SerializerMethodField()
    latest_status_update = serializers.SerializerMethodField()
    is_favorite = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            "id", "name", "description", "color", "organization",
            "is_archived", "health", "issue_prefix", "latest_status_update",
            "tasks_count", "completed_tasks_count",
            "sprints_count", "epics_count", "is_favorite",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "is_favorite", "created_at", "updated_at"]

    def validate_organization(self, value):
        """Solo el owner/admin de la org puede asignar proyectos a ella."""
        if value is None:
            return value
        request = self.context.get("request")
        if request:
            from apps.collaboration.views import _user_is_org_admin
            if not _user_is_org_admin(request.user, value):
                raise serializers.ValidationError(
                    "Debes ser admin de la organización para asignarle proyectos."
                )
        return value

    def get_tasks_count(self, obj):
        # Usa la anotación del queryset si existe (evita N+1 en list)
        ann = getattr(obj, "tasks_count_ann", None)
        return ann if ann is not None else obj.tasks.count()

    def get_completed_tasks_count(self, obj):
        ann = getattr(obj, "completed_tasks_count_ann", None)
        return (
            ann
            if ann is not None
            else obj.tasks.filter(state="completed").count()
        )

    def get_sprints_count(self, obj):
        ann = getattr(obj, "sprints_count_ann", None)
        return ann if ann is not None else obj.sprints.count()

    def get_epics_count(self, obj):
        ann = getattr(obj, "epics_count_ann", None)
        return ann if ann is not None else obj.epics.count()

    def get_is_favorite(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        # Con prefetch (get_queryset) esto no lanza query extra
        return any(u.id == request.user.id for u in obj.favorited_by.all())

    def get_latest_status_update(self, obj):
        """Último ProjectStatusUpdate como dict (o None).

        Usa el prefetch ``_status_updates_prefetched`` del queryset si
        existe (patrón ``*_count_ann``); si no, hace una sola query.
        """
        updates = getattr(obj, "_status_updates_prefetched", None)
        if updates is None:
            updates = list(
                obj.status_updates.select_related("author")[:1]
            )
        latest = updates[0] if updates else None
        if latest is None:
            return None
        return {
            "health": latest.health,
            "note": latest.note,
            "author_email": (
                latest.author.email if latest.author_id else None
            ),
            "created_at": latest.created_at.isoformat(),
        }


class ProjectStatusUpdateSerializer(serializers.ModelSerializer):
    author_email = serializers.CharField(source="author.email", read_only=True)

    class Meta:
        model = ProjectStatusUpdate
        fields = [
            "id", "project", "health", "note",
            "author", "author_email", "created_at",
        ]
        read_only_fields = ["id", "author", "created_at"]

    def validate_project(self, value):
        """Crear un status update requiere permiso de escritura → 403."""
        request = self.context.get("request")
        if request:
            from rest_framework.exceptions import PermissionDenied

            from .models import accessible_projects
            if not accessible_projects(
                request.user, write=True
            ).filter(id=value.id).exists():
                raise PermissionDenied(
                    "El proyecto no existe o no tienes permiso de edición."
                )
        return value


class ProjectRiskSerializer(serializers.ModelSerializer):
    severity = serializers.IntegerField(read_only=True)
    owner_email = serializers.CharField(source="owner.email", read_only=True)

    class Meta:
        model = ProjectRisk
        fields = [
            "id", "project", "title", "description", "probability",
            "impact", "severity", "status", "mitigation",
            "owner_email", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "severity", "created_at", "updated_at"]


class ProjectSectionSerializer(serializers.ModelSerializer):
    class Meta:
        from .models import ProjectSection
        model = ProjectSection
        fields = ["id", "project", "name", "order", "created_at"]
        read_only_fields = ["id", "created_at"]


class PortfolioSerializer(serializers.ModelSerializer):
    project_ids = serializers.PrimaryKeyRelatedField(
        source="projects",
        many=True,
        queryset=Project.objects.all(),
        required=False,
    )

    class Meta:
        from .models import Portfolio
        model = Portfolio
        fields = ["id", "name", "color", "project_ids", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_project_ids(self, value):
        """Todos los proyectos deben ser accesibles por el usuario."""
        request = self.context.get("request")
        if request and value:
            from .models import accessible_projects
            allowed = accessible_projects(request.user)
            foreign = [p.id for p in value if not allowed.filter(id=p.id).exists()]
            if foreign:
                raise serializers.ValidationError(
                    f"Proyectos inexistentes o sin acceso: {foreign}"
                )
        return value


class ProjectTemplateSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    is_mine = serializers.SerializerMethodField()

    class Meta:
        from .models import ProjectTemplate
        model = ProjectTemplate
        fields = [
            "id", "name", "description", "config", "is_builtin",
            "is_public", "use_count", "author", "is_mine", "created_at",
        ]
        read_only_fields = [
            "id", "is_builtin", "use_count", "author", "is_mine",
            "created_at",
        ]

    def get_author(self, obj):
        return obj.owner.username or obj.owner.email

    def get_is_mine(self, obj):
        request = self.context.get("request")
        return bool(request and obj.owner_id == request.user.id)

    def validate_config(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("config debe ser un objeto JSON.")
        tasks = value.get("tasks", [])
        if not isinstance(tasks, list):
            raise serializers.ValidationError("config.tasks debe ser una lista.")
        return value


class ProjectStateLabelSerializer(serializers.ModelSerializer):
    class Meta:
        from .models import ProjectStateLabel
        model = ProjectStateLabel
        fields = ["id", "project", "state", "label", "created_at"]
        read_only_fields = ["id", "created_at"]
        # El endpoint hace upsert por (project, state): el validator
        # unique_together de DRF rechazaría el segundo POST con 400.
        validators: list = []

    def validate_project(self, value):
        """Requiere permiso de escritura sobre el proyecto → 403 si no."""
        request = self.context.get("request")
        if request:
            from rest_framework.exceptions import PermissionDenied

            from .models import accessible_projects
            if not accessible_projects(
                request.user, write=True
            ).filter(id=value.id).exists():
                raise PermissionDenied(
                    "El proyecto no existe o no tienes permiso de edición."
                )
        return value

    def validate_state(self, value):
        # Import lazy: tasks importa projects (circular a nivel de módulo).
        from apps.tasks.models import Task
        valid = {c[0] for c in Task.State.choices}
        if value not in valid:
            raise serializers.ValidationError(f"Estado inválido: {value}")
        return value


class WorkflowTransitionSerializer(serializers.ModelSerializer):
    class Meta:
        from .models import WorkflowTransition
        model = WorkflowTransition
        fields = ["id", "project", "from_state", "to_state", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_project(self, value):
        request = self.context.get("request")
        if request:
            from .models import accessible_projects
            if not accessible_projects(request.user, write=True).filter(id=value.id).exists():
                raise serializers.ValidationError(
                    "El proyecto no existe o no tienes permiso de edición."
                )
        return value

    def validate(self, data):
        from apps.tasks.models import Task
        valid = {c[0] for c in Task.State.choices}
        for field in ("from_state", "to_state"):
            v = data.get(field, getattr(self.instance, field, None))
            if v not in valid:
                raise serializers.ValidationError({field: f"Estado inválido: {v}"})
        if data.get("from_state") == data.get("to_state") or (
            self.instance and data.get("from_state", self.instance.from_state)
            == data.get("to_state", self.instance.to_state)
        ):
            raise serializers.ValidationError("Una transición no puede ir al mismo estado.")
        return data
