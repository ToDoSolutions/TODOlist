from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import (
    Project,
    ProjectRisk,
    ProjectSection,
    ProjectStatusUpdate,
    derive_issue_prefix,
)
from .serializers import (
    ProjectRiskSerializer,
    ProjectSectionSerializer,
    ProjectSerializer,
    ProjectStatusUpdateSerializer,
)


class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer
    filterset_fields = ["is_archived"]
    search_fields = ["name", "description"]
    ordering_fields = ["created_at", "updated_at", "name"]

    def get_queryset(self):
        if self.action in ("list", "retrieve"):
            # Propios + proyectos donde el usuario es miembro
            from .models import accessible_projects
            qs = accessible_projects(self.request.user)
        else:
            # Crear/editar/borrar: solo proyectos propios
            qs = Project.objects.filter(owner=self.request.user)
        archived = self.request.query_params.get("archived")
        if archived is None:
            qs = qs.filter(is_archived=False)
        if self.request.query_params.get("favorite") == "true":
            qs = qs.filter(favorited_by=self.request.user)
        # Anotar counts para el serializer (evita 3 queries por proyecto).
        # annotate() limpia el ordering del Meta → restaurarlo explícito.
        # Prefetch de status updates para latest_status_update sin N+1.
        from django.db.models import Count, Prefetch, Q
        return qs.annotate(
            tasks_count_ann=Count("tasks", distinct=True),
            sprints_count_ann=Count("sprints", distinct=True),
            epics_count_ann=Count("epics", distinct=True),
            completed_tasks_count_ann=Count(
                "tasks", filter=Q(tasks__state="completed"), distinct=True
            ),
        ).prefetch_related(
            "favorited_by",
            Prefetch(
                "status_updates",
                queryset=ProjectStatusUpdate.objects.select_related("author"),
                to_attr="_status_updates_prefetched",
            )
        ).order_by(*Project._meta.ordering)

    def perform_create(self, serializer):
        # issue_prefix: se respeta si viene en el payload; si va en
        # blanco se deriva del nombre ("Mi Proyecto" → "MP").
        prefix = serializer.validated_data.get("issue_prefix") or (
            derive_issue_prefix(serializer.validated_data.get("name", ""))
        )
        serializer.save(owner=self.request.user, issue_prefix=prefix)

    def _get_accessible(self, pk):
        """Proyecto por pk dentro del scope de lectura (para acciones
        personales como favorito, que también aplican a compartidos)."""
        from django.shortcuts import get_object_or_404

        from .models import accessible_projects
        return get_object_or_404(
            accessible_projects(self.request.user), pk=pk
        )

    @action(detail=True, methods=["post"])
    def favorite(self, request, pk=None):
        """Marca el proyecto como favorito del usuario (idempotente)."""
        project = self._get_accessible(pk)
        project.favorited_by.add(request.user)
        return Response({"favorite": True})

    @action(detail=True, methods=["post", "delete"])
    def unfavorite(self, request, pk=None):
        """Quita el proyecto de favoritos (idempotente)."""
        project = self._get_accessible(pk)
        project.favorited_by.remove(request.user)
        return Response({"favorite": False})


class ProjectSectionViewSet(viewsets.ModelViewSet):
    """Secciones de proyecto (columnas tipo Todoist/Asana).

    Lectura: miembros del proyecto — el list exige ``?project=<id>``.
    Escritura (create/update/order/delete/reorder): owner/editor del
    proyecto (misma política que ProjectRiskViewSet).
    """

    serializer_class = ProjectSectionSerializer
    filterset_fields = ["project"]

    def get_queryset(self):
        from .models import accessible_projects
        write = self.action in (
            "create", "update", "partial_update", "destroy", "reorder",
        )
        return ProjectSection.objects.filter(
            project__in=accessible_projects(self.request.user, write=write)
        ).select_related("project")

    def list(self, request, *args, **kwargs):
        if not request.query_params.get("project"):
            return Response(
                {"project": "El parámetro ?project=<id> es requerido."},
                status=400,
            )
        return super().list(request, *args, **kwargs)

    def perform_create(self, serializer):
        # Validación de objeto: el proyecto destino debe ser editable
        # por el usuario (un viewer no puede crear secciones en él).
        from rest_framework.exceptions import PermissionDenied

        from .models import accessible_projects
        project = serializer.validated_data.get("project")
        if project and not accessible_projects(
            self.request.user, write=True
        ).filter(id=project.id).exists():
            raise PermissionDenied(
                "Solo owner/editor del proyecto puede crear secciones"
            )
        serializer.save()

    @action(detail=False, methods=["post"])
    def reorder(self, request):
        """Asigna ``order`` secuencial según ``section_ids``.

        Body: {"project": <id>, "section_ids": [<id>, ...]}. Todas las
        secciones deben pertenecer al proyecto indicado (escritura).
        """
        from .models import accessible_projects
        project_id = request.data.get("project")
        section_ids = request.data.get("section_ids")
        if not project_id or not isinstance(section_ids, list) or not section_ids:
            return Response(
                {"error": "project y section_ids son requeridos"},
                status=400,
            )
        if not accessible_projects(
            request.user, write=True
        ).filter(id=project_id).exists():
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied(
                "El proyecto no existe o no tienes permiso de edición."
            )
        sections = {
            s.id: s
            for s in ProjectSection.objects.filter(
                project_id=project_id, id__in=section_ids
            )
        }
        missing = [i for i in section_ids if i not in sections]
        if missing:
            return Response(
                {"error": f"Secciones inexistentes en el proyecto: {missing[:5]}"},
                status=400,
            )
        for pos, sid in enumerate(section_ids):
            sections[sid].order = pos
        ProjectSection.objects.bulk_update(sections.values(), ["order"])
        return Response({"updated": len(section_ids)})


class ProjectStatusUpdateViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Updates de estado de proyecto (inmutables, como KeyResultUpdate).

    Lectura: cualquiera con acceso de lectura al proyecto (filtrar con
    ?project=<id>). Creación: requiere permiso de escritura sobre el
    proyecto y sincroniza ``project.health`` con el health del update.
    Borrado: solo el autor del update (los ajenos → 404).
    """

    serializer_class = ProjectStatusUpdateSerializer
    filterset_fields = ["project"]

    def get_queryset(self):
        from .models import accessible_projects
        qs = ProjectStatusUpdate.objects.filter(
            project__in=accessible_projects(self.request.user)
        ).select_related("project", "author")
        if self.action == "destroy":
            # Solo el autor puede borrar su update (ajenos → 404).
            qs = qs.filter(author=self.request.user)
        return qs

    def perform_create(self, serializer):
        update = serializer.save(author=self.request.user)
        # Sincronizar el health actual del proyecto con el del update.
        project = update.project
        project.health = update.health
        project.save(update_fields=["health", "updated_at"])


class ProjectRiskViewSet(viewsets.ModelViewSet):
    """Riesgos de proyecto. Lectura: miembros; escritura: owner/editor."""

    serializer_class = ProjectRiskSerializer
    filterset_fields = ["project", "status", "probability", "impact"]
    search_fields = ["title", "description"]

    def get_queryset(self):
        from .models import accessible_projects
        write = self.action in (
            "create", "update", "partial_update", "destroy"
        )
        projects = accessible_projects(self.request.user, write=write)
        return ProjectRisk.objects.filter(
            project__in=projects
        ).select_related("project", "owner")

    def perform_create(self, serializer):
        # Validación de objeto: el proyecto destino debe ser editable
        # por el usuario (un viewer no puede crear riesgos en él).
        from rest_framework.exceptions import PermissionDenied
        project = serializer.validated_data.get("project")
        from .models import accessible_projects
        if project and not accessible_projects(
            self.request.user, write=True
        ).filter(id=project.id).exists():
            raise PermissionDenied(
                "Solo owner/editor del proyecto puede crear riesgos"
            )
        serializer.save(owner=self.request.user)


class PortfolioViewSet(viewsets.ModelViewSet):
    """Portfolios personales: agrupaciones de proyectos del usuario."""

    def get_serializer_class(self):
        from .serializers import PortfolioSerializer
        return PortfolioSerializer

    def get_queryset(self):
        from .models import Portfolio
        return Portfolio.objects.filter(
            owner=self.request.user
        ).prefetch_related("projects")

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class ProjectTemplateViewSet(viewsets.ModelViewSet):
    """Plantillas de proyecto. Propias + builtin visibles para todos."""

    def get_serializer_class(self):
        from .serializers import ProjectTemplateSerializer
        return ProjectTemplateSerializer

    def get_queryset(self):
        from django.db.models import Q

        from .models import ProjectTemplate
        qs = ProjectTemplate.objects.filter(
            Q(owner=self.request.user) | Q(is_builtin=True)
        )
        if self.action in ("update", "partial_update", "destroy"):
            # Solo el owner edita/borra (una builtin visible no es editable
            # por cualquiera).
            qs = qs.filter(owner=self.request.user)
        return qs

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=["post"])
    def apply(self, request, pk=None):
        """Crea un proyecto nuevo aplicando la plantilla.

        Body: {"name": str, "description"?: str}
        Crea el proyecto (owner=request.user) + tareas de config.tasks +
        tags (get_or_create por nombre) adjuntados a las tareas creadas +
        state labels de config.state_labels.
        """
        from apps.tasks.models import Task
        template = self.get_object()
        name = request.data.get("name")
        if not name:
            return Response({"name": "Este campo es requerido."}, status=400)
        project = Project.objects.create(
            owner=request.user,
            name=name,
            description=request.data.get("description", ""),
        )
        config = template.config or {}
        valid_states = {c[0] for c in Task.State.choices}
        valid_priorities = {c[0] for c in Task.Priority.choices}
        valid_types = {c[0] for c in Task.Type.choices}
        created_tasks = []
        for t in config.get("tasks", []):
            if not isinstance(t, dict):
                continue
            state = t.get("state", Task.State.PENDING)
            priority = t.get("priority", Task.Priority.P3_MEDIUM)
            task_type = t.get("task_type", Task.Type.TASK)
            created_tasks.append(Task.objects.create(
                owner=request.user,
                project=project,
                title=t.get("title") or "Sin título",
                description=t.get("description", ""),
                state=state if state in valid_states else Task.State.PENDING,
                priority=(
                    priority if priority in valid_priorities
                    else Task.Priority.P3_MEDIUM
                ),
                task_type=(
                    task_type if task_type in valid_types else Task.Type.TASK
                ),
                estimate_hours=t.get("estimate_hours"),
            ))
        tag_names = config.get("tags", [])
        if tag_names and created_tasks:
            from apps.tags.models import Tag
            tags = [
                Tag.objects.get_or_create(owner=request.user, name=n)[0]
                for n in tag_names
            ]
            for task in created_tasks:
                task.tags.set(tags)
        state_labels = config.get("state_labels", {})
        if state_labels:
            from .models import ProjectStateLabel
            for state, label in state_labels.items():
                if state in valid_states:
                    ProjectStateLabel.objects.update_or_create(
                        project=project, state=state,
                        defaults={"label": str(label)[:50]},
                    )
        return Response({
            "project_id": project.id,
            "tasks_created": len(created_tasks),
        }, status=201)

    @action(detail=False, methods=["post"])
    def from_project(self, request):
        """Snapshot de un proyecto existente en una nueva plantilla.

        Body: {"project_id": int, "name": str, "description"?: str}
        Requiere acceso de lectura al proyecto.
        """
        from rest_framework.exceptions import PermissionDenied

        from .models import ProjectTemplate, accessible_projects
        project_id = request.data.get("project_id")
        name = request.data.get("name")
        if not project_id or not name:
            return Response(
                {"detail": "project_id y name son requeridos."}, status=400)
        project = accessible_projects(request.user).filter(
            id=project_id).first()
        if project is None:
            raise PermissionDenied(
                "El proyecto no existe o no tienes acceso."
            )
        project_tasks = list(project.tasks.prefetch_related("tags"))
        tasks = [{
            "title": t.title,
            "description": t.description,
            "priority": t.priority,
            "task_type": t.task_type,
            "state": t.state,
            "estimate_hours": (
                float(t.estimate_hours) if t.estimate_hours is not None else None
            ),
        } for t in project_tasks]
        tag_names = sorted({
            tag.name for t in project_tasks for tag in t.tags.all()
        })
        config = {
            "tasks": tasks,
            "tags": tag_names,
            "state_labels": {
                sl.state: sl.label for sl in project.state_labels.all()
            },
        }
        template = ProjectTemplate.objects.create(
            owner=request.user,
            name=name,
            description=request.data.get("description", ""),
            config=config,
        )
        serializer = self.get_serializer(template)
        return Response(serializer.data, status=201)


class ProjectStateLabelViewSet(viewsets.ModelViewSet):
    """Labels personalizadas por estado dentro de un proyecto.

    Lectura: miembros del proyecto (filtrar con ?project=<id>).
    Escritura: owner/editor (create hace upsert por (project, state)).
    """

    def get_serializer_class(self):
        from .serializers import ProjectStateLabelSerializer
        return ProjectStateLabelSerializer

    def get_queryset(self):
        from .models import ProjectStateLabel, accessible_projects
        write = self.action in ("update", "partial_update", "destroy")
        qs = ProjectStateLabel.objects.filter(
            project__in=accessible_projects(self.request.user, write=write)
        ).select_related("project")
        project_id = self.request.query_params.get("project")
        if project_id:
            qs = qs.filter(project_id=project_id)
        return qs

    def create(self, request, *args, **kwargs):
        """Upsert por unique_together (project, state)."""
        from .models import ProjectStateLabel
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        obj, created = ProjectStateLabel.objects.update_or_create(
            project=data["project"],
            state=data["state"],
            defaults={"label": data["label"]},
        )
        out = self.get_serializer(obj)
        return Response(out.data, status=201 if created else 200)


class WorkflowTransitionViewSet(viewsets.ModelViewSet):
    """Transiciones de workflow por proyecto.

    Lectura: cualquier miembro del proyecto. Escritura: quien tenga permiso
    de edición (owner/editor, o admin de la org del proyecto).
    """

    def get_serializer_class(self):
        from .serializers import WorkflowTransitionSerializer
        return WorkflowTransitionSerializer

    def get_queryset(self):
        from .models import WorkflowTransition, accessible_projects
        write = self.action in (
            "create", "update", "partial_update", "destroy"
        )
        return WorkflowTransition.objects.filter(
            project__in=accessible_projects(self.request.user, write=write)
        ).select_related("project")
