import contextlib
import secrets

from django.utils.dateparse import parse_datetime
from rest_framework import status, viewsets
from rest_framework.decorators import (
    action,
    api_view,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.users.api_auth import IntakePublicRateThrottle

from .models import IntakeForm, IntakeSubmission
from .serializers import IntakeFormSerializer, IntakeSubmissionSerializer


class IntakeFormViewSet(viewsets.ModelViewSet):
    """Formularios de intake del usuario + submissions.

    POST /api/intake-forms/{id}/submit/ {"data": {...}} → valida el schema
    y crea la tarea en el proyecto destino.
    """

    serializer_class = IntakeFormSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["project", "enabled"]

    def get_queryset(self):
        # Propios + formularios de proyectos accesibles (los miembros
        # pueden listar/ver el formulario pero solo owner lo gestiona)
        from apps.projects.models import accessible_projects
        write = self.action in (
            "create", "update", "partial_update", "destroy",
            "rotate_public_token",
        )
        if write:
            return IntakeForm.objects.filter(owner=self.request.user)
        from django.db.models import Count
        return IntakeForm.objects.filter(
            project__in=accessible_projects(self.request.user)
        ).select_related("project", "owner").annotate(
            submissions_count_ann=Count("submissions", distinct=True)
        )

    def perform_create(self, serializer):
        # El proyecto destino del formulario debe ser editable
        from rest_framework.exceptions import PermissionDenied
        project = serializer.validated_data.get("project")
        from apps.projects.models import accessible_projects
        if project and not accessible_projects(
            self.request.user, write=True
        ).filter(id=project.id).exists():
            raise PermissionDenied(
                "Solo owner/editor del proyecto puede crear formularios"
            )
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        """Envía una submission: valida schema y crea la tarea.

        Requiere permiso de escritura sobre el proyecto destino — el canal
        para no-miembros es el submit público por token.
        """
        form = self.get_object()
        if not form.enabled:
            return Response(
                {"error": "El formulario está deshabilitado"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from apps.projects.models import accessible_projects
        if form.project_id and not accessible_projects(
            request.user, write=True
        ).filter(pk=form.project_id).exists():
            return Response(
                {"error": "Necesitas permiso de escritura en el proyecto"},
                status=status.HTTP_403_FORBIDDEN,
            )
        data = request.data.get("data", {})
        errors = validate_form_data(form, data)
        if errors:
            return Response({"errors": errors},
                            status=status.HTTP_400_BAD_REQUEST)

        from django.db import transaction
        with transaction.atomic():
            task = create_task_from_form(form, data, request.user)
            submission = IntakeSubmission.objects.create(
                form=form, submitted_by=request.user, data=data, task=task,
            )
        return Response({
            "submission_id": submission.id,
            "task_id": task.id,
            "task_title": task.title,
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def rotate_public_token(self, request, pk=None):
        """Regenera el token público del formulario (solo owner).

        Invalida la URL pública anterior: las submissions con el token
        viejo pasan a 404.
        """
        form = self.get_object()
        form.public_token = secrets.token_urlsafe(32)
        form.save(update_fields=["public_token"])
        return Response({"public_token": form.public_token})

    def _validate_data(self, form, data):
        return validate_form_data(form, data)

    def _create_task(self, form, data, user):
        return create_task_from_form(form, data, user)


def validate_form_data(form, data):
    """Valida los datos contra el schema del formulario."""
    errors = []
    for field in form.schema:
        name = field["name"]
        value = data.get(name)
        if field.get("required") and (value is None or value == ""):
            errors.append(f"'{field.get('label', name)}' es requerido")
            continue
        if value is None or value == "":
            continue
        ftype = field.get("type", "text")
        if ftype == "number":
            try:
                float(value)
            except (TypeError, ValueError):
                errors.append(f"'{name}' debe ser numérico")
        elif ftype == "select" and value not in field.get("options", []):
            errors.append(f"'{name}' no es una opción válida")
        elif ftype == "checkbox" and not isinstance(value, bool):
            errors.append(f"'{name}' debe ser booleano")
    return errors


def create_task_from_form(form, data, user):
    """Crea la Task mapeando campos reservados + el resto a descripción."""
    from apps.tasks.models import Task

    task_kwargs = {"owner": user, "project": form.project}
    extra_lines = []
    for field in form.schema:
        name = field["name"]
        value = data.get(name)
        if value is None or value == "":
            value = field.get("default")
        if value is None or value == "":
            continue
        if name == "title":
            task_kwargs["title"] = str(value)[:255]
        elif name == "description":
            task_kwargs["description"] = str(value)
        elif name == "priority":
            with contextlib.suppress(TypeError, ValueError):
                p = int(value)
                if p in [c[0] for c in Task.Priority.choices]:
                    task_kwargs["priority"] = p
        elif name == "due_date":
            dt = parse_datetime(str(value))
            if dt:
                task_kwargs["due_date"] = dt
        elif name == "assignee":
            # Lookup por email/username/id. Si no resuelve (o no tiene
            # acceso al proyecto), el valor cae a extra_lines para no
            # perder el dato.
            assignee = resolve_assignee(value, form.project)
            if assignee is not None:
                task_kwargs["assignee"] = assignee
            else:
                label = field.get("label", name)
                extra_lines.append(f"**{label}:** {value}")
        else:
            label = field.get("label", name)
            extra_lines.append(f"**{label}:** {value}")

    task_kwargs.setdefault("title", form.name)
    if extra_lines:
        desc = task_kwargs.get("description", "")
        extra = "\n".join(extra_lines)
        task_kwargs["description"] = (
            f"{desc}\n\n---\n{extra}" if desc else extra
        )

    defaults = form.task_defaults or {}
    task_kwargs.setdefault("state", defaults.get("state", "pending"))
    if defaults.get("priority") is not None:
        task_kwargs.setdefault("priority", defaults["priority"])
    if defaults.get("task_type"):
        task_kwargs.setdefault("task_type", defaults["task_type"])

    # Paridad con TaskViewSet.perform_create: position al final de la
    # lista del usuario y seq por proyecto canónico (ref "MP-12").
    from apps.tasks.services import next_position_seq

    pos, seq = next_position_seq(user, form.project)
    task_kwargs.setdefault("position", pos)
    task_kwargs.setdefault("seq", seq)

    task = Task.objects.create(**task_kwargs)
    # Multi-homing desde task_defaults: solo proyectos con permiso de
    # escritura para el owner del formulario (y nunca el canónico).
    extra_ids = defaults.get("extra_projects") or []
    if extra_ids:
        from apps.projects.models import accessible_projects
        allowed = accessible_projects(user, write=True).exclude(pk=task.project_id)
        task.extra_projects.set(allowed.filter(pk__in=extra_ids))
    for tag_name in defaults.get("tags", []):
        from apps.tags.models import Tag
        tag, _ = Tag.objects.get_or_create(owner=user, name=tag_name)
        task.tags.add(tag)
    return task


def resolve_assignee(value, project):
    """Resuelve el valor de un campo 'assignee' a un User.

    Acepta email (case-insensitive), username o id numérico. Si el
    formulario está ligado a un proyecto, el usuario debe tener acceso
    (owner o miembro). Devuelve None si no resuelve.
    """
    from django.contrib.auth import get_user_model

    User = get_user_model()
    text = str(value).strip()
    user = (
        User.objects.filter(email__iexact=text).first()
        or User.objects.filter(username__iexact=text).first()
    )
    if user is None and text.isdigit():
        user = User.objects.filter(id=int(text)).first()
    if user is None:
        return None
    if project is not None:
        has_access = (
            user == project.owner
            or project.members.filter(user=user).exists()
        )
        if not has_access:
            return None
    return user


class IntakeSubmissionViewSet(viewsets.ReadOnlyModelViewSet):
    """Submissions enviadas (auditoría)."""
    serializer_class = IntakeSubmissionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        from apps.projects.models import accessible_projects
        qs = IntakeSubmission.objects.filter(
            form__project__in=accessible_projects(self.request.user)
        ).select_related("form", "task", "submitted_by")
        form_id = self.request.query_params.get("form")
        if form_id:
            qs = qs.filter(form_id=form_id)
        return qs


@api_view(["GET"])
@permission_classes([AllowAny])
@throttle_classes([IntakePublicRateThrottle])
def public_intake_schema(request, token):
    """GET /api/intake-forms/public/{token}/ — esquema público del formulario.

    Devuelve los metadatos y el schema de campos para que un frontend
    público pueda renderizar el formulario antes de hacer submit.
    404 si el token no existe o el formulario está deshabilitado.
    """
    form = (
        IntakeForm.objects
        .filter(public_token=token, enabled=True)
        .first()
    )
    if form is None:
        return Response(
            {"error": "Formulario no encontrado"},
            status=status.HTTP_404_NOT_FOUND,
        )
    return Response({
        "id": form.id,
        "name": form.name,
        "description": form.description,
        "schema": form.schema,
        "enabled": form.enabled,
    })


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([IntakePublicRateThrottle])
def public_intake_submit(request, token):
    """POST /api/intake-forms/public/{token}/submit/ — submission anónima.

    Resuelve el formulario por su public_token (404 si no existe o está
    deshabilitado), valida los datos contra el schema con la misma lógica
    del submit autenticado y crea la tarea a nombre del owner del
    formulario. La submission queda registrada con submitted_by=owner.

    El body acepta {"data": {...}} (mismo formato que el submit
    autenticado) o los campos en raíz.
    """
    form = (
        IntakeForm.objects
        .filter(public_token=token, enabled=True)
        .select_related("project", "owner")
        .first()
    )
    if form is None:
        return Response(
            {"error": "Formulario no encontrado"},
            status=status.HTTP_404_NOT_FOUND,
        )

    data = request.data.get("data")
    if not isinstance(data, dict):
        # Fallback: campos en raíz del body
        data = {
            k: v for k, v in request.data.items() if k != "data"
        }
    errors = validate_form_data(form, data)
    if errors:
        return Response(
            {"errors": errors}, status=status.HTTP_400_BAD_REQUEST
        )

    from django.db import transaction
    with transaction.atomic():
        task = create_task_from_form(form, data, form.owner)
        IntakeSubmission.objects.create(
            form=form, submitted_by=form.owner, data=data, task=task,
        )
    return Response({"id": task.id}, status=status.HTTP_201_CREATED)
