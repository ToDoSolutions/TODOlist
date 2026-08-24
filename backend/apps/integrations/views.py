"""Views de la API de integraciones con GitHub."""
import secrets

from django.conf import settings
from django.shortcuts import redirect
from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from apps.tasks.models import Task
from .github_client import GitHubAppClient, GitHubOAuthClient
from .models import (
    GitHubInstallation, GitHubRepo, GitHubIssueLink,
    GitHubPullRequest, GitHubCommit, GitHubRelease, GitHubCheckRun,
)
from .serializers import (
    GitHubInstallationSerializer,
    GitHubRepoSerializer,
    GitHubIssueLinkSerializer,
    ImportIssuesSerializer,
    CreateIssueSerializer,
    GitHubPullRequestSerializer,
    GitHubCommitSerializer,
    GitHubReleaseSerializer,
    GitHubCheckRunSerializer,
)
from .sync_service import (
    create_issue_for_task,
    import_issue_as_task,
    sync_repo_issues,
    sync_task_to_issue,
)
from .tasks import sync_repo_issues_task


class GitHubInstallationViewSet(
    mixins.ListModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Gestión de instalaciones de GitHub del usuario."""
    serializer_class = GitHubInstallationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return GitHubInstallation.objects.filter(user=self.request.user)

    @action(detail=False, methods=["get"])
    def repos(self, request):
        """Lista los repos sincronizados del usuario."""
        repos = GitHubRepo.objects.filter(installation__user=request.user)
        serializer = GitHubRepoSerializer(repos, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def discover_repos(self, request):
        """Descubre repos disponibles en la instalación de GitHub."""
        installations = self.get_queryset()
        if not installations.exists():
            return Response(
                {"error": "No hay instalaciones de GitHub conectadas"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        inst = installations.first()
        client = GitHubAppClient(installation_id=inst.installation_id)
        try:
            gh_repos = client.list_installation_repos()
        except Exception as e:
            return Response(
                {"error": f"Error al listar repos: {str(e)}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # Sincronizar repos a la BD
        created = 0
        for r in gh_repos:
            _, was_created = GitHubRepo.objects.get_or_create(
                installation=inst,
                repo_id=r["id"],
                defaults={
                    "full_name": r["full_name"],
                    "name": r["name"],
                    "owner": r["owner"]["login"],
                    "is_private": r["private"],
                    "default_branch": r.get("default_branch", "main"),
                },
            )
            if was_created:
                created += 1

        return Response({
            "total": len(gh_repos),
            "new": created,
            "message": f"Se encontraron {len(gh_repos)} repos, {created} nuevos",
        })


class GitHubRepoViewSet(
    mixins.ListModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Gestión de repos sincronizados."""
    serializer_class = GitHubRepoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return GitHubRepo.objects.filter(installation__user=self.request.user)

    @action(detail=True, methods=["post"])
    def sync(self, request, pk=None):
        """Dispara la sincronización de issues de un repo."""
        repo = self.get_object()
        if not repo.sync_enabled:
            return Response(
                {"error": "La sincronización está deshabilitada para este repo"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Ejecutar de forma asíncrona con Celery
        sync_repo_issues_task.delay(repo.id)
        return Response({"message": f"Sincronización encolada para {repo.full_name}"})

    @action(detail=True, methods=["get"])
    def issues(self, request, pk=None):
        """Lista los issues de un repo en GitHub (no los locales)."""
        repo = self.get_object()
        state = request.query_params.get("state", "open")
        client = GitHubAppClient(
            installation_id=repo.installation.installation_id
        )
        try:
            issues = client.list_issues(repo.owner, repo.name, state=state)
        except Exception as e:
            return Response(
                {"error": f"Error al listar issues: {str(e)}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        # Filtrar PRs
        issues = [i for i in issues if "pull_request" not in i]
        return Response({
            "results": [
                {
                    "id": i["id"],
                    "number": i["number"],
                    "title": i["title"],
                    "state": i["state"],
                    "html_url": i["html_url"],
                    "body": (i.get("body") or "")[:500],
                    "labels": [l["name"] for l in i.get("labels", [])],
                    "already_linked": GitHubIssueLink.objects.filter(
                        repo=repo, issue_number=i["number"]
                    ).exists(),
                }
                for i in issues
            ]
        })

    @action(detail=True, methods=["post"])
    def import_issues(self, request, pk=None):
        """Importa issues de GitHub como tareas locales."""
        repo = self.get_object()
        serializer = ImportIssuesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        state = serializer.validated_data.get("state", "open")
        label_filter = serializer.validated_data.get("label_filter", "")

        client = GitHubAppClient(
            installation_id=repo.installation.installation_id
        )
        issues = client.list_issues(repo.owner, repo.name, state=state)
        issues = [i for i in issues if "pull_request" not in i]

        if label_filter:
            issues = [
                i for i in issues
                if label_filter in [l["name"] for l in i.get("labels", [])]
            ]

        imported = 0
        skipped = 0
        for issue_data in issues:
            _, created = import_issue_as_task(issue_data, repo, request.user)
            if created:
                imported += 1
            else:
                skipped += 1

        return Response({
            "imported": imported,
            "skipped": skipped,
            "total": len(issues),
        })


class GitHubIssueLinkViewSet(
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """Links entre tareas e issues de GitHub."""
    serializer_class = GitHubIssueLinkSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return GitHubIssueLink.objects.filter(
            task__owner=self.request.user
        ).select_related("repo", "task")

    @action(detail=False, methods=["post"])
    def create_for_task(self, request):
        """Crea un issue en GitHub para una tarea existente."""
        serializer = CreateIssueSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        task_id = serializer.validated_data["task_id"]
        repo_id = serializer.validated_data["repo_id"]

        try:
            task = Task.objects.get(id=task_id, owner=request.user)
        except Task.DoesNotExist:
            return Response(
                {"error": "Tarea no encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            repo = GitHubRepo.objects.get(
                id=repo_id, installation__user=request.user
            )
        except GitHubRepo.DoesNotExist:
            return Response(
                {"error": "Repo no encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if hasattr(task, "github_link"):
            return Response(
                {"error": "La tarea ya tiene un issue vinculado"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            link = create_issue_for_task(task, repo)
        except Exception as e:
            return Response(
                {"error": f"Error creando issue: {str(e)}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            GitHubIssueLinkSerializer(link).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def sync(self, request, pk=None):
        """Fuerza la sincronización de un link específico."""
        link = self.get_object()
        try:
            sync_task_to_issue(link.task)
        except Exception as e:
            return Response(
                {"error": f"Error sincronizando: {str(e)}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response({"message": "Sincronización completada"})


# --- Pull Requests, Commits, Releases, CI ---

class GitHubPullRequestViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Lista y detalle de PRs sincronizados."""
    serializer_class = GitHubPullRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return GitHubPullRequest.objects.filter(
            repo__installation__user=self.request.user
        ).select_related("repo")

    @action(detail=True, methods=["post"])
    def link_task(self, request, pk=None):
        """Vincula manualmente un PR a una tarea."""
        pr = self.get_object()
        task_id = request.data.get("task_id")
        if not task_id:
            return Response(
                {"error": "task_id requerido"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from apps.tasks.models import Task
        try:
            task = Task.objects.get(id=task_id, owner=request.user)
        except Task.DoesNotExist:
            return Response(
                {"error": "Tarea no encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )
        pr.tasks.add(task)
        return Response({"message": f"PR #{pr.pr_number} vinculado a tarea {task_id}"})


class GitHubCommitViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Lista y detalle de commits sincronizados."""
    serializer_class = GitHubCommitSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return GitHubCommit.objects.filter(
            repo__installation__user=self.request.user
        ).select_related("repo")


class GitHubReleaseViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Lista y detalle de releases sincronizados."""
    serializer_class = GitHubReleaseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return GitHubRelease.objects.filter(
            repo__installation__user=self.request.user
        ).select_related("repo")

    @action(detail=True, methods=["get"])
    def progress(self, request, pk=None):
        """Progreso de una release: tareas completadas vs pendientes."""
        release = self.get_object()
        tasks = release.tasks.all()
        total = tasks.count()
        done = tasks.filter(state="completed").count()
        prs = release.pull_requests.all()
        prs_merged = prs.filter(is_merged=True).count()
        return Response({
            "tasks_total": total,
            "tasks_done": done,
            "tasks_pending": total - done,
            "prs_total": prs.count(),
            "prs_merged": prs_merged,
            "prs_pending": prs.count() - prs_merged,
            "progress_pct": round((done / total * 100) if total > 0 else 0, 1),
        })


class GitHubCheckRunViewSet(
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """Lista de check runs (CI/CD)."""
    serializer_class = GitHubCheckRunSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return GitHubCheckRun.objects.filter(
            repo__installation__user=self.request.user
        ).select_related("repo", "pull_request")


# --- OAuth Login con GitHub ---

@api_view(["GET"])
@permission_classes([AllowAny])
def github_oauth_start(request):
    """Inicia el flujo OAuth de GitHub: redirige a la URL de autorización."""
    frontend_url = settings.DJANGO_FRONTEND_URL
    redirect_uri = f"{frontend_url.rstrip('/')}/auth/github/callback"
    state = secrets.token_urlsafe(32)
    request.session["github_oauth_state"] = state

    oauth = GitHubOAuthClient()
    auth_url = oauth.get_authorize_url(redirect_uri, state)
    return Response({"auth_url": auth_url, "state": state})


@api_view(["POST"])
@permission_classes([AllowAny])
def github_oauth_callback(request):
    """Callback del flujo OAuth: intercambia code por token y crea/linka usuario."""
    code = request.data.get("code")
    state = request.data.get("state")
    stored_state = request.session.get("github_oauth_state")

    if not code or not state or state != stored_state:
        return Response(
            {"error": "Parámetros OAuth inválidos"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    frontend_url = settings.DJANGO_FRONTEND_URL
    redirect_uri = f"{frontend_url.rstrip('/')}/auth/github/callback"

    oauth = GitHubOAuthClient()
    try:
        token_data = oauth.exchange_code(code, redirect_uri)
    except Exception as e:
        return Response(
            {"error": f"Error intercambiando código: {str(e)}"},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    access_token = token_data.get("access_token")
    if not access_token:
        return Response(
            {"error": "No se obtuvo access_token"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        gh_user = oauth.get_user_info(access_token)
    except Exception as e:
        return Response(
            {"error": f"Error obteniendo info de usuario: {str(e)}"},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    # Buscar o crear usuario local
    from apps.users.models import User
    from rest_framework_simplejwt.tokens import RefreshToken

    gh_email = gh_user.get("email")
    gh_username = gh_user.get("login", "")
    gh_user_id = gh_user.get("id")

    # Buscar por github_user_id en instalaciones existentes
    user = None
    existing_inst = GitHubInstallation.objects.filter(
        github_user_id=gh_user_id
    ).first()
    if existing_inst:
        user = existing_inst.user

    # Si no, buscar por email
    if not user and gh_email:
        user = User.objects.filter(email=gh_email).first()

    # Crear usuario si no existe
    if not user:
        if not gh_email:
            gh_email = f"{gh_username}@github.local"
        user = User.objects.create_user(
            email=gh_email,
            username=gh_username,
            password=secrets.token_urlsafe(32),
        )

    # Crear/actualizar instalación
    inst, _ = GitHubInstallation.objects.update_or_create(
        github_user_id=gh_user_id,
        defaults={
            "user": user,
            "installation_id": gh_user_id,  # OAuth usa user id como installation ref
            "account_login": gh_username,
            "account_type": "User",
            "avatar_url": gh_user.get("avatar_url", ""),
            "github_username": gh_username,
            "access_token": access_token,
        },
    )

    # Generar JWT tokens
    refresh = RefreshToken.for_user(user)
    return Response({
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "user": {
            "id": user.id,
            "email": user.email,
            "username": user.username,
        },
        "github_username": gh_username,
    })


# --- Webhook receiver ---

@api_view(["POST"])
@permission_classes([AllowAny])
def github_webhook(request):
    """Recibe webhooks de GitHub con idempotencia y reintentos."""
    import json

    # Verificar firma
    signature = request.headers.get("X-Hub-Signature-256", "")
    body = request.body
    if not GitHubAppClient.verify_webhook_signature(body, signature):
        return Response(
            {"error": "Firma inválida"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    event_type = request.headers.get("X-GitHub-Event", "")
    delivery_id = request.headers.get("X-GitHub-Delivery", "")
    payload = json.loads(body)
    action = payload.get("action", "")
    repo_full_name = payload.get("repository", {}).get("full_name", "")

    # Procesar con idempotencia
    from .webhook_processor import process_webhook_delivery
    result, status_code = process_webhook_delivery(
        delivery_id=delivery_id,
        event_type=event_type,
        action=action,
        payload=payload,
        repo_full_name=repo_full_name,
    )

    return Response(result, status=status_code)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def webhook_deliveries(request):
    """Lista las entregas de webhooks para auditoría."""
    from .models import WebhookDelivery
    from .serializers import WebhookDeliverySerializer

    deliveries = WebhookDelivery.objects.all()[:50]
    serializer = WebhookDeliverySerializer(deliveries, many=True)
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def webhook_retry_dead_letter(request):
    """Reintenta manualmente las entregas en DLQ."""
    from .webhook_processor import retry_dead_letter_deliveries
    result = retry_dead_letter_deliveries()
    return Response({"message": result})
