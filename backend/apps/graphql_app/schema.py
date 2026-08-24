"""Schema GraphQL con graphene-django."""
import graphene
from graphene_django.types import DjangoObjectType

from apps.tasks.models import Task, Comment, Sprint
from apps.projects.models import Project
from apps.tags.models import Tag


def login_required(func):
    """Decorator que verifica autenticación via DRF JWT."""
    def wrapper(self, info, **kwargs):
        request = info.context
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            raise Exception("Authentication required")
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
        return self.tasks.count()


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
        return Project.objects.filter(owner=info.context.user, is_archived=False)

    @login_required
    def resolve_project(self, info, id):
        return Project.objects.filter(owner=info.context.user, id=id).first()

    @login_required
    def resolve_all_sprints(self, info, project_id=None):
        qs = Sprint.objects.filter(project__owner=info.context.user)
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
        from datetime import datetime
        project = Project.objects.filter(owner=info.context.user, id=project_id).first()
        if not project:
            raise Exception("Proyecto no encontrado")
        task = Task.objects.create(
            owner=info.context.user,
            project=project,
            title=title,
            description=description,
            priority=priority,
            due_date=due_date,
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
        qs = Task.objects.for_user(info.context.user)
        task = qs.filter(id=id).first()
        if not task:
            raise Exception("Tarea no encontrada")
        if title is not None:
            task.title = title
        if state is not None:
            task.state = state
        if priority is not None:
            task.priority = priority
        task.save()
        return UpdateTaskMutation(task=task)


class DeleteTaskMutation(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)

    success = graphene.Boolean()

    @login_required
    def mutate(self, info, id):
        qs = Task.objects.for_user(info.context.user)
        task = qs.filter(id=id).first()
        if not task:
            raise Exception("Tarea no encontrada")
        task.delete()
        return DeleteTaskMutation(success=True)


class Mutation(graphene.ObjectType):
    create_task = CreateTaskMutation.Field()
    update_task = UpdateTaskMutation.Field()
    delete_task = DeleteTaskMutation.Field()


schema = graphene.Schema(query=Query, mutation=Mutation)
