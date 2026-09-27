"""Schema GraphQL con graphene-django."""
import graphene
from django.db.models import Q
from graphene_django.types import DjangoObjectType
from graphql import GraphQLError
from graphql.language import ast as gql_ast

from apps.projects.models import Project
from apps.tags.models import Tag
from apps.tasks.models import Comment, Sprint, Task

# Profundidad máxima permitida en queries GraphQL (anti-DoS)
MAX_QUERY_DEPTH = 8


def _measure_depth(node, fragments, depth=0):
    """Mide la profundidad de un selection set (incl. fragments inline)."""
    if node is None or not getattr(node, "selection_set", None):
        return depth
    max_d = depth
    for sel in node.selection_set.selections:
        if isinstance(sel, gql_ast.FieldNode):
            max_d = max(max_d, _measure_depth(sel, fragments, depth + 1))
        elif isinstance(sel, gql_ast.InlineFragmentNode):
            max_d = max(max_d, _measure_depth(sel, fragments, depth))
        elif isinstance(sel, gql_ast.FragmentSpreadNode):
            frag = fragments.get(sel.name.value)
            if frag:
                max_d = max(max_d, _measure_depth(frag, fragments, depth + 1))
    return max_d


class DepthLimitMiddleware:
    """Middleware GraphQL: rechaza queries con profundidad excesiva."""

    def resolve(self, next_, root, info, **args):
        ctx = info.context
        if not getattr(ctx, "_gql_depth_checked", False):
            ctx._gql_depth_checked = True
            frag_map = dict(getattr(info, "fragments", None) or {})
            depth = _measure_depth(info.operation, frag_map)
            if depth > MAX_QUERY_DEPTH:
                raise GraphQLError(
                    f"Query depth {depth} exceeds maximum {MAX_QUERY_DEPTH}"
                )
        return next_(root, info, **args)


def login_required(func):
    """Decorator que verifica autenticación via DRF JWT."""
    def wrapper(self, info, **kwargs):
        request = info.context
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            raise GraphQLError("Authentication required")
        return func(self, info, **kwargs)
    return wrapper


class TaskType(DjangoObjectType):
    class Meta:
        model = Task
        fields = (
            "id", "title", "description", "state", "priority",
            "due_date", "story_points", "task_type", "created_at",
            "updated_at", "completed_at", "project", "sprint",
            "epic", "parent", "owner",
        )


class ProjectType(DjangoObjectType):
    task_count = graphene.Int()

    class Meta:
        model = Project
        fields = ("id", "name", "description", "color", "is_archived", "created_at")

    def resolve_task_count(self, info):
        return self.tasks.count()  # pylint: disable=no-member


class SprintType(DjangoObjectType):
    class Meta:
        model = Sprint
        fields = ("id", "name", "goal", "state", "start_date", "end_date", "project")


class TagType(DjangoObjectType):
    class Meta:
        model = Tag
        fields = ("id", "name", "color")


class CommentType(DjangoObjectType):
    class Meta:
        model = Comment
        fields = ("id", "body", "author", "created_at", "task")


class Query(graphene.ObjectType):
    # Queries
    all_tasks = graphene.List(TaskType, project_id=graphene.Int(), state=graphene.String())
    task = graphene.Field(TaskType, id=graphene.Int(required=True))
    all_projects = graphene.List(ProjectType)
    project = graphene.Field(ProjectType, id=graphene.Int(required=True))
    all_sprints = graphene.List(SprintType, project_id=graphene.Int())
    all_tags = graphene.List(TagType)

    @login_required
    def resolve_all_tasks(self, info, project_id=None, state=None):
        qs = Task.objects.for_user(info.context.user).select_related(
            "project", "sprint", "epic", "parent", "owner"
        ).prefetch_related("tags", "subtasks")
        if project_id:
            qs = qs.filter(project_id=project_id)
        if state:
            qs = qs.filter(state=state)
        return qs

    @login_required
    def resolve_task(self, info, id):
        qs = Task.objects.for_user(info.context.user)
        return qs.filter(id=id).first()

    @login_required
    def resolve_all_projects(self, info):
        from apps.projects.models import accessible_projects
        return accessible_projects(info.context.user).filter(is_archived=False)

    @login_required
    def resolve_project(self, info, id):
        from apps.projects.models import accessible_projects
        return accessible_projects(info.context.user).filter(id=id).first()

    @login_required
    def resolve_all_sprints(self, info, project_id=None):
        from apps.projects.models import accessible_projects
        qs = Sprint.objects.filter(
            Q(owner=info.context.user)
            | Q(project__in=accessible_projects(info.context.user))
        )
        if project_id:
            qs = qs.filter(project_id=project_id)
        return qs

    @login_required
    def resolve_all_tags(self, info):
        return Tag.objects.filter(owner=info.context.user)


class CreateTaskMutation(graphene.Mutation):
    class Arguments:
        title = graphene.String(required=True)
        project_id = graphene.Int(required=True)
        description = graphene.String()
        priority = graphene.Int()
        due_date = graphene.String()

    task = graphene.Field(TaskType)

    @login_required
    def mutate(self, info, title, project_id, description="", priority=3, due_date=None):
        from apps.projects.models import accessible_projects
        from apps.tasks.services import (
            normalize_title,
            parse_due_date,
            validate_priority,
        )
        project = accessible_projects(
            info.context.user, write=True
        ).filter(id=project_id).first()
        if not project:
            raise GraphQLError("Proyecto no encontrado")
        try:
            title = normalize_title(title)
            validate_priority(priority)
            parsed_due = parse_due_date(due_date)
        except ValueError as e:
            raise GraphQLError(str(e))
        task = Task.objects.create(
            owner=info.context.user,
            project=project,
            title=title,
            description=description,
            priority=priority,
            due_date=parsed_due,
        )
        return CreateTaskMutation(task=task)


class UpdateTaskMutation(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
        title = graphene.String()
        state = graphene.String()
        priority = graphene.Int()

    task = graphene.Field(TaskType)

    @login_required
    def mutate(self, info, id, title=None, state=None, priority=None):
        from apps.tasks.services import UNSET, get_editable_task, update_task
        # write=True: consistente con REST (rol viewer no puede mutar)
        task = get_editable_task(info.context.user, id)
        if not task:
            raise GraphQLError("Tarea no encontrada")
        try:
            task = update_task(
                task,
                title=title if title is not None else UNSET,
                state=state if state is not None else UNSET,
                priority=priority if priority is not None else UNSET,
            )
        except ValueError as e:
            raise GraphQLError(str(e))
        return UpdateTaskMutation(task=task)


class DeleteTaskMutation(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)

    success = graphene.Boolean()

    @login_required
    def mutate(self, info, id):
        qs = Task.objects.for_user(info.context.user, write=True)
        task = qs.filter(id=id).first()
        if not task:
            raise GraphQLError("Tarea no encontrada")
        task.delete()
        return DeleteTaskMutation(success=True)


class Mutation(graphene.ObjectType):
    create_task = CreateTaskMutation.Field()
    update_task = UpdateTaskMutation.Field()
    delete_task = DeleteTaskMutation.Field()


schema = graphene.Schema(query=Query, mutation=Mutation)
