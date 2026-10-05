from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from apps.projects.models import Project, ProjectSection
from apps.tags.models import Tag

from .models import (
    Attachment,
    Comment,
    CustomField,
    CustomFieldValue,
    Epic,
    OutgoingWebhook,
    RecurrenceRule,
    SavedSearch,
    Sprint,
    Subtask,
    Task,
    TaskActivity,
    TaskApproval,
    TaskRelation,
    TaskTemplate,
    TimeEntry,
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
    replies_count = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ["id", "body", "author_email", "parent", "replies_count",
                  "reactions", "created_at", "updated_at"]
        read_only_fields = ["id", "author_email", "replies_count",
                            "reactions", "created_at", "updated_at"]

    def get_replies_count(self, obj):
        ann = getattr(obj, "replies_count_ann", None)
        return ann if ann is not None else obj.replies.count()

    def validate_parent(self, value):
        """El padre debe ser un comentario de la misma tarea y no puede
        ser respuesta de otra respuesta (threading de un solo nivel)."""
        task = self.initial_data.get("task") or getattr(
            self.instance, "task_id", None
        )
        if task and value.task_id != int(task):
            raise serializers.ValidationError(
                "El comentario padre debe pertenecer a la misma tarea."
            )
        if value.parent_id:
            raise serializers.ValidationError(
                "Solo se permite un nivel de anidación."
            )
        return value


def _dependency_path_exists(from_task, to_task, exclude=None, max_nodes=500):
    """True si existe un camino de dependencia from_task → … → to_task.

    Recorre aristas "depende de": X depends_on Y (X→Y) y X blocks Y (Y→X).
    BFS con límite de nodos para evitar recorridos desbocados en grafos densos.
    """
    if from_task.id == to_task.id:
        return True
    visited = {from_task.id}
    queue = [from_task.id]
    excluded = (
        (exclude.source_id, exclude.target_id, exclude.relation_type)
        if exclude and exclude.id
        else None
    )
    while queue and len(visited) < max_nodes:
        node_id = queue.pop(0)
        # depends_on: node → target; blocks: (source blocks node) → node depende de source
        edges = list(
            TaskRelation.objects.filter(
                source_id=node_id,
                relation_type=TaskRelation.RelationType.DEPENDS_ON,
            ).values_list("source_id", "target_id", "relation_type")
        ) + list(
            TaskRelation.objects.filter(
                target_id=node_id,
                relation_type=TaskRelation.RelationType.BLOCKS,
            ).values_list("source_id", "target_id", "relation_type")
        )
        for s_id, t_id, r_type in edges:
            if excluded and (s_id, t_id, r_type) == excluded:
                continue
            # La arista "depende de" va del dependiente al dependido
            nid = t_id if r_type == TaskRelation.RelationType.DEPENDS_ON else s_id
            if nid == to_task.id:
                return True
            if nid not in visited:
                visited.add(nid)
                queue.append(nid)
    return False


class TaskRelationSerializer(serializers.ModelSerializer):
    source_title = serializers.CharField(source="source.title", read_only=True)
    target_title = serializers.CharField(source="target.title", read_only=True)
    # Opcional en payload: la vista anidada (/tasks/{id}/relations/) lo
    # inyecta por contexto; el ViewSet directo lo exige en validate().
    # mypy: el nombre "source" colisiona con Field.source (str|None) — es
    # el nombre público del campo de la API, no se puede renombrar.
    source = serializers.PrimaryKeyRelatedField(  # type: ignore[assignment]
        queryset=Task.objects.all(), required=False
    )

    class Meta:
        model = TaskRelation
        fields = ["id", "source", "source_title", "target", "target_title",
                  "relation_type", "created_at"]
        read_only_fields = ["id", "source_title", "target_title", "created_at"]
        # unique_together validado manualmente: el validator automático
        # exigiría `source` en el payload (la vista anidada lo inyecta por
        # contexto) y devolvería IntegrityError→500 en vez de 400.
        validators: list = []

    def validate(self, data):
        target = data.get("target")
        if not target:
            raise serializers.ValidationError("Debes especificar una tarea objetivo.")
        request = self.context.get("request")
        # source llega por payload (ViewSet directo) o por contexto (vista
        # anidada /tasks/{id}/relations/) — sin esto los checks de
        # auto-relación y circularidad nunca se ejecutaban al crear.
        source = (
            data.get("source")
            or self.context.get("source")
            or getattr(self.instance, "source", None)
        )
        if request and source is None:
            raise serializers.ValidationError(
                "Debes especificar la tarea origen."
            )
        if request and not Task.objects.for_user(
            request.user, write=True
        ).filter(id=source.id).exists():
            raise serializers.ValidationError(
                "La tarea origen no existe o no tienes permiso de edición."
            )
        # El target debe ser editable por el usuario (IDOR + info leak por timing)
        if request and not Task.objects.for_user(request.user, write=True).filter(id=target.id).exists():
            raise serializers.ValidationError("La tarea objetivo no existe o no tienes permiso de edición.")
        if source and target and source.id == target.id:
            raise serializers.ValidationError("Una tarea no puede relacionarse consigo misma.")
        # Evitar dependencia circular: directa (A↔B) y transitiva (A→B→C→A).
        # Arista normalizada "depende de": depends_on va source→target;
        # blocks va target→source (el bloqueado depende del bloqueante).
        relation_type = data.get("relation_type", getattr(self.instance, "relation_type", None))
        if source and target and relation_type in ("blocks", "depends_on"):
            dep_from, dep_to = (
                (target, source) if relation_type == "blocks" else (source, target)
            )
            # La misma arista ya existe en la otra representación
            # (X depends_on Y ≡ Y blocks X): sería un duplicado semántico.
            alt = TaskRelation.objects.filter(
                source=dep_from, target=dep_to,
                relation_type=TaskRelation.RelationType.DEPENDS_ON,
            ) | TaskRelation.objects.filter(
                source=dep_to, target=dep_from,
                relation_type=TaskRelation.RelationType.BLOCKS,
            )
            if self.instance:
                alt = alt.exclude(id=self.instance.id)
            if alt.exists():
                raise serializers.ValidationError(
                    "Dependencia duplicada: la relación inversa ya existe."
                )
            if _dependency_path_exists(dep_to, dep_from, exclude=self.instance):
                raise serializers.ValidationError(
                    "Dependencia circular: la relación crearía un ciclo en la cadena de bloqueos."
                )
        # unique_together manual (validators=[] arriba)
        if source and target and relation_type:
            dup = TaskRelation.objects.filter(
                source=source, target=target, relation_type=relation_type
            )
            if self.instance:
                dup = dup.exclude(id=self.instance.id)
            if dup.exists():
                raise serializers.ValidationError(
                    "Ya existe una relación idéntica entre estas tareas."
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
        # Usa la anotación del queryset si existe (evita N+1 en list)
        ann = getattr(obj, "task_count_ann", None)
        return ann if ann is not None else obj.tasks.count()

    def validate_project(self, value):
        if value is None:
            return value
        request = self.context.get("request")
        if request:
            from apps.projects.models import accessible_projects
            if not accessible_projects(request.user, write=True).filter(id=value.id).exists():
                raise serializers.ValidationError(
                    "El proyecto no existe o no tienes permiso de edición."
                )
        return value

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
        ann = getattr(obj, "progress_done_ann", None)
        return ann if ann is not None else obj.progress[0]

    def get_progress_total(self, obj):
        ann = getattr(obj, "progress_total_ann", None)
        return ann if ann is not None else obj.progress[1]

    def validate_project(self, value):
        if value is None:
            return value
        request = self.context.get("request")
        if request:
            from apps.projects.models import accessible_projects
            if not accessible_projects(request.user, write=True).filter(id=value.id).exists():
                raise serializers.ValidationError(
                    "El proyecto no existe o no tienes permiso de edición."
                )
        return value

    def validate(self, data):
        start = data.get("start_date", getattr(self.instance, "start_date", None))
        end = data.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end < start:
            raise serializers.ValidationError(
                "La fecha de fin de la épica debe ser posterior a la de inicio."
            )
        return data


class SavedSearchSerializer(serializers.ModelSerializer):
    is_owner = serializers.SerializerMethodField()

    class Meta:
        model = SavedSearch
        fields = ["id", "name", "filters", "is_shared", "is_owner",
                  "created_at", "updated_at"]
        read_only_fields = ["id", "is_owner", "created_at", "updated_at"]

    def get_is_owner(self, obj):
        request = self.context.get("request")
        return request is not None and obj.owner_id == request.user.id


class TaskApprovalSerializer(serializers.ModelSerializer):
    """Solicitud/decisión de aprobación embebida en TaskSerializer."""

    requester_email = serializers.CharField(
        source="requester.email", read_only=True
    )
    approver_email = serializers.CharField(
        source="approver.email", read_only=True
    )

    class Meta:
        model = TaskApproval
        fields = [
            "id", "requester", "requester_email",
            "approver", "approver_email",
            "status", "note", "decision_note",
            "created_at", "decided_at",
        ]
        read_only_fields = fields


class TaskSerializer(serializers.ModelSerializer):
    subtasks = SubtaskSerializer(many=True, read_only=True)
    comments = CommentSerializer(many=True, read_only=True)
    tags_ids: serializers.PrimaryKeyRelatedField = serializers.PrimaryKeyRelatedField(
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
    assignee_email = serializers.CharField(source="assignee.email", read_only=True)
    assignees: serializers.PrimaryKeyRelatedField = serializers.PrimaryKeyRelatedField(
        many=True, read_only=True
    )
    assignees_detail = serializers.SerializerMethodField()
    watchers: serializers.PrimaryKeyRelatedField = serializers.PrimaryKeyRelatedField(
        many=True, read_only=True
    )
    is_watching = serializers.SerializerMethodField()
    is_favorite = serializers.SerializerMethodField()
    approvals = TaskApprovalSerializer(many=True, read_only=True)
    pending_approval_for_me = serializers.SerializerMethodField()
    logged_seconds = serializers.SerializerMethodField()
    section = serializers.PrimaryKeyRelatedField(
        queryset=ProjectSection.objects.all(),
        required=False,
        allow_null=True,
    )
    section_name = serializers.CharField(source="section.name", read_only=True)
    ref = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            "id", "ref", "seq", "title", "description", "state", "priority",
            "task_type",
            "due_date", "start_date", "completed_at",
            "reminder_at", "reminder_sent",
            "story_points", "estimate_hours", "size",
            "project", "extra_projects", "tags", "tags_ids",
            "recurrence",
            "parent", "parent_title",
            "sprint", "sprint_name",
            "epic", "epic_title",
            "section", "section_name",
            "assignee", "assignee_email",
            "assignees", "assignees_detail",
            "watchers", "is_watching",
            "relations", "activities",
            "subtask_done", "subtask_total",
            "subtasks", "comments",
            "approvals", "pending_approval_for_me", "logged_seconds",
            "position", "is_pinned", "is_milestone", "is_favorite",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "ref", "seq", "completed_at", "reminder_sent",
            "assignees", "assignees_detail", "watchers", "is_watching",
            "extra_projects",
            "approvals", "pending_approval_for_me", "logged_seconds",
            "position", "is_favorite",
            "created_at", "updated_at",
        ]

    def get_ref(self, obj):
        """Ref legible estilo Linear/Jira: "MP-12".

        Solo cuando la tarea tiene proyecto con ``issue_prefix`` y un
        ``seq`` asignado; en otro caso cae al id numérico.
        """
        if obj.project_id and obj.seq and obj.project.issue_prefix:
            return f"{obj.project.issue_prefix}-{obj.seq}"
        return str(obj.id)

    def get_subtask_done(self, obj):
        return obj.subtask_progress[0]

    def get_subtask_total(self, obj):
        return obj.subtask_progress[1]

    def get_assignees_detail(self, obj):
        return [
            {"id": u.id, "email": u.email, "username": u.username}
            for u in obj.assignees.all()
        ]

    def get_is_watching(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        # Con prefetch (get_queryset) esto no lanza query extra
        return any(u.id == request.user.id for u in obj.watchers.all())

    def get_is_favorite(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        # Con prefetch (get_queryset) esto no lanza query extra
        return any(u.id == request.user.id for u in obj.favorited_by.all())

    def get_pending_approval_for_me(self, obj):
        """True si el approval pendiente más reciente me toca decidir a mí."""
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        # approvals está prefetch + ordenado -created_at: el primer
        # pendiente en memoria es el último solicitado
        latest_pending = next(
            (
                a for a in obj.approvals.all()
                if a.status == TaskApproval.Status.PENDING
            ),
            None,
        )
        return bool(
            latest_pending and latest_pending.approver_id == request.user.id
        )

    def get_logged_seconds(self, obj):
        """Segundos registrados (TimeEntry) sobre la tarea.

        Usa la anotación ``logged_seconds_ann`` del queryset (subquery,
        inmune al fan-out de los joins de for_user); sin anotación
        cae a la suma en memoria/por instancia.
        """
        ann = getattr(obj, "logged_seconds_ann", None)
        if ann is not None:
            return int(ann)
        return sum(e.duration_seconds for e in obj.time_entries.all())


class TaskCreateUpdateSerializer(serializers.ModelSerializer):
    tags = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Tag.objects.none(), required=False
    )
    assignees = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=get_user_model().objects.all(),
        required=False,
    )
    recurrence_data = RecurrenceRuleSerializer(write_only=True, required=False)
    # Multi-homing: hogares adicionales (project sigue siendo el canónico)
    extra_projects = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Project.objects.none(), required=False
    )

    class Meta:
        model = Task
        fields = [
            "id", "title", "description", "state", "priority", "task_type",
            "due_date", "start_date", "reminder_at",
            "story_points", "estimate_hours", "size",
            "project", "extra_projects", "tags", "recurrence_data",
            "parent", "sprint", "epic", "section",
            "assignee", "assignees",
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
            # Solo hogares extra con permiso de escritura
            from apps.projects.models import accessible_projects
            self.fields["extra_projects"].child_relation.queryset = (
                accessible_projects(request.user, write=True)
            )

    def validate_project(self, value):
        if value is None:
            return value
        request = self.context.get("request")
        if request:
            from apps.projects.models import accessible_projects
            if not accessible_projects(request.user, write=True).filter(id=value.id).exists():
                raise serializers.ValidationError("El proyecto no existe o no tienes permiso de edición.")
        return value

    def validate_sprint(self, value):
        if value is None:
            return value
        request = self.context.get("request")
        if request:
            from django.db.models import Q

            from apps.projects.models import accessible_projects
            ok = Sprint.objects.filter(
                Q(owner=request.user)
                | Q(project__in=accessible_projects(request.user, write=True)),
                id=value.id,
            ).exists()
            if not ok:
                raise serializers.ValidationError("El sprint no existe o no tienes permiso de edición.")
        return value

    def validate_epic(self, value):
        if value is None:
            return value
        request = self.context.get("request")
        if request:
            from django.db.models import Q

            from apps.projects.models import accessible_projects
            ok = Epic.objects.filter(
                Q(owner=request.user)
                | Q(project__in=accessible_projects(request.user, write=True)),
                id=value.id,
            ).exists()
            if not ok:
                raise serializers.ValidationError("La épica no existe o no tienes permiso de edición.")
        return value

    def validate_section(self, value):
        if value is None:
            return value
        request = self.context.get("request")
        if request:
            from apps.projects.models import accessible_projects
            ok = accessible_projects(request.user, write=True).filter(
                id=value.project_id
            ).exists()
            if not ok:
                raise serializers.ValidationError(
                    "La sección no existe o no tienes permiso de edición."
                )
        return value

    def validate_assignee(self, value):
        if value is None:
            return value
        request = self.context.get("request")
        if not request:
            return value
        # El assignee debe tener acceso al proyecto de la tarea (si tiene)
        project = self.initial_data.get("project") or getattr(self.instance, "project", None)
        project_id = project.id if hasattr(project, "id") else project
        if project_id:
            proj = Project.objects.filter(id=project_id).first()
            if proj and value.id != proj.owner_id and not proj.members.filter(user=value).exists():
                raise serializers.ValidationError(
                    "El responsable no tiene acceso al proyecto."
                )
        return value

    def validate_parent(self, value):
        """Evita ciclos jerarquicos."""
        if value is None:
            return value
        request = self.context.get("request")
        if request and not Task.objects.for_user(request.user, write=True).filter(id=value.id).exists():
            raise serializers.ValidationError("La tarea padre no existe o no tienes permiso de edición.")
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

    def validate_state(self, value):
        """Respeta el workflow del proyecto si tiene transiciones definidas."""
        if self.instance:
            from .services import assert_state_transition
            try:
                assert_state_transition(self.instance, value)
            except ValueError as e:
                raise serializers.ValidationError(str(e))
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
        # La sección debe pertenecer al mismo proyecto que la tarea
        # (una tarea sin proyecto no puede tener sección).
        section = data.get("section", getattr(self.instance, "section", None))
        if section and (project is None or section.project_id != project.id):
            raise serializers.ValidationError(
                "La sección debe pertenecer al mismo proyecto que la tarea."
            )
        # El proyecto canónico no puede ser a la vez un hogar extra
        extras = data.get("extra_projects")
        if extras and project and any(p.id == project.id for p in extras):
            raise serializers.ValidationError(
                {"extra_projects": "El proyecto principal no puede ser también un hogar extra."}
            )
        # No permitir due_date en el pasado para tareas nuevas
        due_date = data.get("due_date")
        if due_date and not self.instance:
            today = timezone.now().date()
            d = due_date.date() if hasattr(due_date, "date") else due_date
            if d < today:
                raise serializers.ValidationError(
                    "No puedes crear una tarea con fecha de vencimiento en el pasado."
                )
        return data

    def create(self, validated_data):
        tags = validated_data.pop("tags", [])
        assignees = validated_data.pop("assignees", [])
        extra_projects = validated_data.pop("extra_projects", [])
        recurrence_data = validated_data.pop("recurrence_data", None)
        if recurrence_data:
            recurrence = RecurrenceRule.objects.create(**recurrence_data)
            validated_data["recurrence"] = recurrence
        task = Task.objects.create(**validated_data)
        if tags:
            task.tags.set(tags)
        if assignees:
            task.assignees.set(assignees)
        if extra_projects:
            task.extra_projects.set(extra_projects)
        # Registrar actividad
        TaskActivity.objects.create(
            task=task,
            actor=task.owner,
            action=TaskActivity.ActionType.CREATED,
        )
        return task

    def update(self, instance, validated_data):
        tags = validated_data.pop("tags", None)
        assignees = validated_data.pop("assignees", None)
        extra_projects = validated_data.pop("extra_projects", None)
        # Si cambia reminder_at, el recordatorio vuelve a estar pendiente
        if (
            "reminder_at" in validated_data
            and validated_data["reminder_at"] != instance.reminder_at
        ):
            instance.reminder_sent = False
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
        if assignees is not None:
            instance.assignees.set(assignees)
        if extra_projects is not None:
            instance.extra_projects.set(extra_projects)
        return instance


class TimeEntrySerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        model = TimeEntry
        fields = [
            "id", "task", "user", "user_email", "duration_seconds",
            "description", "started_at", "ended_at", "is_running",
            "created_at",
        ]
        read_only_fields = ["id", "user", "user_email", "created_at"]

    def validate_task(self, value):
        if value is None:
            raise serializers.ValidationError("Debes asociar el registro de tiempo a una tarea.")
        request = self.context.get("request")
        if request and not Task.objects.for_user(request.user, write=True).filter(id=value.id).exists():
            raise serializers.ValidationError("La tarea no existe o no tienes permiso de edición.")
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

    def validate(self, data):
        # Un registro finalizado siempre debe tener duración positiva
        ended = data.get("ended_at", getattr(self.instance, "ended_at", None))
        duration = data.get(
            "duration_seconds", getattr(self.instance, "duration_seconds", 0)
        )
        if ended and not (duration and duration > 0):
            raise serializers.ValidationError(
                "Un registro de tiempo finalizado debe tener duración mayor que cero."
            )
        return data


class AttachmentSerializer(serializers.ModelSerializer):
    uploaded_by_email = serializers.CharField(source="uploaded_by.email", read_only=True)

    class Meta:
        model = Attachment
        fields = [
            "id", "task", "comment", "uploaded_by", "uploaded_by_email",
            "file", "external_url", "filename", "file_size", "content_type", "created_at",
        ]
        read_only_fields = ["id", "uploaded_by", "uploaded_by_email", "file_size", "content_type", "created_at"]

    def validate(self, data):
        request = self.context.get("request")
        file = data.get("file")
        external_url = data.get("external_url", getattr(self.instance, "external_url", ""))
        if not file and not external_url and not self.instance:
            raise serializers.ValidationError(
                "Debes indicar un fichero o un enlace externo."
            )
        if not request:
            return data
        task = data.get("task", getattr(self.instance, "task", None))
        comment = data.get("comment", getattr(self.instance, "comment", None))
        if task and not Task.objects.for_user(request.user, write=True).filter(id=task.id).exists():
            raise serializers.ValidationError({"task": "La tarea no existe o no tienes permiso de edición."})
        if comment:
            if not Task.objects.for_user(request.user, write=True).filter(id=comment.task_id).exists():
                raise serializers.ValidationError({"comment": "El comentario no existe o no tienes permiso."})
            if task and comment.task_id != task.id:
                raise serializers.ValidationError({"comment": "El comentario no pertenece a la tarea indicada."})
        return data


class TaskTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskTemplate
        fields = [
            "id", "name", "description", "owner", "project",
            "template_data", "created_at",
        ]
        read_only_fields = ["id", "owner", "created_at"]

    def validate_project(self, value):
        if value is None:
            return value
        request = self.context.get("request")
        if request and not Project.objects.filter(id=value.id, owner=request.user).exists():
            raise serializers.ValidationError("El proyecto no existe o no te pertenece.")
        return value


class CustomFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomField
        fields = [
            "id", "project", "name", "field_type", "options",
            "is_required", "default_value", "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate_project(self, value):
        request = self.context.get("request")
        if request:
            from apps.projects.models import accessible_projects
            if not accessible_projects(request.user, write=True).filter(id=value.id).exists():
                raise serializers.ValidationError("El proyecto no existe o no tienes permiso de edición.")
        return value


class CustomFieldValueSerializer(serializers.ModelSerializer):
    field_name = serializers.CharField(source="field.name", read_only=True)  # type: ignore[assignment]

    class Meta:
        model = CustomFieldValue
        fields = ["id", "task", "field", "field_name", "value", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at", "field_name"]

    def validate(self, data):
        request = self.context.get("request")
        if not request:
            return data
        task = data.get("task", getattr(self.instance, "task", None))
        field = data.get("field", getattr(self.instance, "field", None))
        from apps.projects.models import accessible_projects
        if task and not Task.objects.for_user(request.user, write=True).filter(id=task.id).exists():
            raise serializers.ValidationError({"task": "La tarea no existe o no tienes permiso de edición."})
        if field and not CustomField.objects.filter(
            id=field.id, project__in=accessible_projects(request.user, write=True)
        ).exists():
            raise serializers.ValidationError({"field": "El campo no existe o no tienes permiso."})
        # Coherencia: el campo debe pertenecer al proyecto de la tarea
        if task and field and task.project_id and field.project_id != task.project_id:
            raise serializers.ValidationError({"field": "El campo no pertenece al proyecto de la tarea."})
        return data


class OutgoingWebhookSerializer(serializers.ModelSerializer):
    class Meta:
        model = OutgoingWebhook
        fields = [
            "id", "owner", "url", "events", "secret",
            "is_active", "created_at",
        ]
        read_only_fields = ["id", "owner", "created_at"]
        extra_kwargs = {"secret": {"write_only": True}}

    def validate_url(self, value):
        from urllib.parse import urlparse
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise serializers.ValidationError("URL inválida: solo http/https.")
        # SSRF: rechazar destinos internos (misma política que chat)
        from apps.integrations_chat.services import _is_safe_url
        if not _is_safe_url(value):
            raise serializers.ValidationError(
                "URL no permitida: destino interno o no resoluble."
            )
        return value
