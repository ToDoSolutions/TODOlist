"""Views de la API de integraciones con GitHub."""
import logging
import secrets

from django.conf import settings
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import (
    action,
    api_view,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

logger = logging.getLogger(__name__)

from apps.tasks.models import Task
from apps.users.api_auth import InboundRateThrottle

from .github_client import GitHubAppClient, GitHubOAuthClient
from .models import (
    GitHubCheckRun,
    GitHubCommit,
    GitHubInstallation,
    GitHubIssueLink,
    GitHubPullRequest,
    GitHubRelease,
    GitHubRepo,
    InboundWebhook,
)
from .serializers import (
    CreateIssueSerializer,
    GitHubCheckRunSerializer,
    GitHubCommitSerializer,
    GitHubInstallationSerializer,
    GitHubIssueLinkSerializer,
    GitHubPullRequestSerializer,
    GitHubReleaseSerializer,
    GitHubRepoSerializer,
    ImportIssuesSerializer,
    InboundWebhookSerializer,
)
from .sync_service import (
    create_issue_for_task,
    import_issue_as_task,
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
        except Exception:
            logger.exception("Error listando repos de instalación")
            return Response(
                {"error": "Error al listar repos"},
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
        """Dispara la sincronización completa de un repo.

        Sincroniza issues (vía Celery) y PRs, commits, releases y check runs
        de forma síncrona, devolviendo los conteos actualizados.
        """
        repo = self.get_object()
        if not repo.sync_enabled:
            return Response(
                {"error": "La sincronización está deshabilitada para este repo"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Sincronización de issues asíncrona (comportamiento existente)
        sync_repo_issues_task.delay(repo.id)

        # Sincronización activa de PRs, commits, releases y check runs
        from .sync_github import sync_repo_data
        try:
            synced = sync_repo_data(repo)
        except Exception:
            logger.exception("Error sincronizando datos del repo")
            return Response(
                {"error": "Error sincronizando datos del repo"},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response({
            "message": "Sincronización iniciada",
            "synced": synced,
        })

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
        except Exception:
            logger.exception("Error listando issues")
            return Response(
                {"error": "Error al listar issues"},
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

        # Límite de importación masiva (defensa ante repos con miles de issues)
        MAX_IMPORT = 200
        total_available = len(issues)
        issues = issues[:MAX_IMPORT]

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
            "total_available": total_available,
            "truncated": total_available > MAX_IMPORT,
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
            task = Task.objects.for_user(request.user, write=True).get(id=task_id)
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
        except Exception:
            logger.exception("Error creando issue")
            return Response(
                {"error": "Error creando issue"},
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
        except Exception:
            logger.exception("Error en sincronización")
            return Response(
                {"error": "Error sincronizando"},
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
            task = Task.objects.for_user(request.user, write=True).get(id=task_id)
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
def oauth_providers(request):
    """Retorna qué providers OAuth están configurados."""
    return Response({
        "github": bool(settings.GITHUB_APP_CLIENT_ID),
        "google": bool(getattr(settings, "SOCIALACCOUNT_PROVIDERS", {}).get("google", {}).get("APP", {}).get("client_id")),
    })


@api_view(["GET"])
@permission_classes([AllowAny])
def github_oauth_start(request):
    """Inicia el flujo OAuth de GitHub: redirige a la URL de autorización."""
    frontend_url = settings.DJANGO_FRONTEND_URL
    redirect_uri = f"{frontend_url.rstrip('/')}/auth/github/callback"
    state = secrets.token_urlsafe(32)
    request.session["github_oauth_state"] = state
    # Fallback sin cookies: cache con TTL de 10 min (SPA con JWT no envía session cookie)
    from django.core.cache import cache
    cache.set(f"gh_oauth_state:{state}", 1, timeout=600)

    oauth = GitHubOAuthClient()
    auth_url = oauth.get_authorize_url(redirect_uri, state)
    return Response({"auth_url": auth_url, "state": state})


def _consume_oauth_state(state):
    """Valida y consume un state OAuth del cache (single-use)."""
    from django.core.cache import cache
    key = f"gh_oauth_state:{state}"
    if cache.get(key):
        cache.delete(key)
        return True
    return False


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AnonRateThrottle])
def github_oauth_callback(request):
    """Callback del flujo OAuth: intercambia code por token y crea/linka usuario."""
    code = request.data.get("code")
    state = request.data.get("state")
    stored_state = request.session.get("github_oauth_state")

    # Validación de state: sesión o cache (single-use)
    state_ok = bool(state) and (
        state == stored_state
        or _consume_oauth_state(state)
    )
    if not code or not state_ok:
        return Response(
            {"error": "Parámetros OAuth inválidos"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    frontend_url = settings.DJANGO_FRONTEND_URL
    redirect_uri = f"{frontend_url.rstrip('/')}/auth/github/callback"

    oauth = GitHubOAuthClient()
    try:
        token_data = oauth.exchange_code(code, redirect_uri)
    except Exception:
        logger.exception("Error intercambiando código OAuth")
        return Response(
            {"error": "Error intercambiando código"},
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
    except Exception:
        logger.exception("Error obteniendo info de usuario de GitHub")
        return Response(
            {"error": "Error obteniendo info de usuario"},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    # Buscar o crear usuario local
    from rest_framework_simplejwt.tokens import RefreshToken

    from apps.users.models import User

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

    # Vincular por email SOLO si el email está verificado en GitHub
    # (el email público del perfil puede ser no verificado → account takeover)
    if not user and gh_email:
        verified_emails = oauth.get_verified_emails(access_token)
        if gh_email.lower() in verified_emails:
            user = User.objects.filter(email__iexact=gh_email).first()

    # Crear usuario si no existe
    if not user:
        if not gh_email:
            gh_email = f"{gh_username}@github.local"
        user = User.objects.create_user(
            email=gh_email,
            username=gh_username,
            password=secrets.token_urlsafe(32),
        )

    # Si el usuario tiene 2FA activo, el flujo OAuth no puede bypasearlo:
    # exigir login por contraseña + 2FA
    tf = getattr(user, "twofactor", None)
    if tf and tf.is_enabled:
        return Response(
            {"error": "La cuenta requiere autenticación 2FA. Inicia sesión con email y contraseña."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    # Crear/actualizar instalación
    _inst, _ = GitHubInstallation.objects.update_or_create(
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
    import hashlib
    import json

    body = request.body
    # Límite de tamaño de payload (defensa ante payloads inflados)
    if len(body) > 2 * 1024 * 1024:
        return Response(
            {"error": "Payload demasiado grande"},
            status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )

    # Verificar firma
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not GitHubAppClient.verify_webhook_signature(body, signature):
        return Response(
            {"error": "Firma inválida"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return Response(
            {"error": "JSON inválido"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    event_type = request.headers.get("X-GitHub-Event", "")
    # Si falta el header de delivery, derivar un id estable del body para
    # mantener idempotencia (evita que todas las entregas sin id colapsen)
    delivery_id = request.headers.get("X-GitHub-Delivery") or hashlib.sha256(body).hexdigest()
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
    """Lista las entregas de webhooks para auditoría.

    Filtra por los repos del usuario autenticado (vía instalación de GitHub).
    """
    from .models import GitHubRepo, WebhookDelivery
    from .serializers import WebhookDeliverySerializer

    # Obtener los repo_full_name de los repos del usuario
    user_repo_names = GitHubRepo.objects.filter(
        installation__user=request.user
    ).values_list("full_name", flat=True)

    deliveries = WebhookDelivery.objects.filter(
        repo_full_name__in=list(user_repo_names)
    )[:50]
    serializer = WebhookDeliverySerializer(deliveries, many=True)
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def webhook_retry_dead_letter(request):
    """Reintenta manualmente las entregas en DLQ del usuario."""
    from .models import GitHubRepo
    from .webhook_processor import retry_dead_letter_deliveries
    # Solo reintentar entregas de los repos del usuario autenticado
    user_repo_names = GitHubRepo.objects.filter(
        installation__user=request.user
    ).values_list("full_name", flat=True)
    if not user_repo_names:
        return Response({"message": "No tienes repos configurados"}, status=404)
    result = retry_dead_letter_deliveries(repo_full_name__in=list(user_repo_names))
    return Response({"message": result})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dora_metrics(request):
    """Métricas DORA calculadas sobre los datos sync de GitHub.

    Query param opcional ``days`` (default 90): ventana de análisis.
    Devuelve deployment frequency, lead time, change failure rate y MTTR.
    """
    from .dora import get_dora_metrics

    try:
        days = int(request.query_params.get("days", 90))
    except (TypeError, ValueError):
        days = 90
    days = max(1, min(days, 365))
    return Response(get_dora_metrics(request.user, days=days))


# --- Inbound webhooks genéricos (Zapier/Make-style) ---

class InboundWebhookViewSet(viewsets.ModelViewSet):
    """CRUD de webhooks entrantes del usuario.

    POST /api/inbound-webhooks/ {name, project?} → crea el endpoint
    personal POST /api/inbound/{token}/. Owner-scoped.
    """
    serializer_class = InboundWebhookSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return InboundWebhook.objects.filter(
            user=self.request.user
        ).select_related("project")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


def _parse_inbound_due_date(value):
    """Acepta ISO datetime o date; devuelve datetime aware o None."""
    if not value:
        return None
    from django.utils import timezone
    from django.utils.dateparse import parse_date, parse_datetime
    dt = parse_datetime(str(value))
    if dt is not None:
        return timezone.make_aware(dt) if timezone.is_naive(dt) else dt
    d = parse_date(str(value))
    if d is not None:
        import datetime as _dt
        return timezone.make_aware(_dt.datetime.combine(d, _dt.time.min))
    return None


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([InboundRateThrottle])
def inbound_webhook(request, token):
    """POST /api/inbound/{token}/ — crea una tarea sin autenticación.

    Body: {title (requerido), description?, priority?(0-5), due_date?(ISO),
    tags?[]}. La tarea se crea a nombre de webhook.user en webhook.project
    (o el primer proyecto del usuario). Actualiza last_used_at.
    """
    from django.utils import timezone

    webhook = (
        InboundWebhook.objects
        .filter(token=token, is_active=True)
        .select_related("user", "project")
        .first()
    )
    if webhook is None:
        return Response(
            {"error": "Webhook no encontrado"},
            status=status.HTTP_404_NOT_FOUND,
        )

    title = (request.data.get("title") or "").strip()
    if not title:
        return Response(
            {"error": "title requerido"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    priority = request.data.get("priority", 3)
    try:
        priority = int(priority)
    except (TypeError, ValueError):
        priority = -1
    if not 0 <= priority <= 5:
        return Response(
            {"error": "priority debe ser un entero entre 0 y 5"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    due_date_raw = request.data.get("due_date")
    due_date = _parse_inbound_due_date(due_date_raw)
    if due_date_raw and due_date is None:
        return Response(
            {"error": "due_date debe ser una fecha ISO válida"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    tags = request.data.get("tags") or []
    if not isinstance(tags, list):
        return Response(
            {"error": "tags debe ser una lista"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    from apps.projects.models import Project
    project = webhook.project or Project.objects.filter(
        owner=webhook.user
    ).first()

    task = Task.objects.create(
        owner=webhook.user,
        project=project,
        title=title[:255],
        description=request.data.get("description") or "",
        priority=priority,
        due_date=due_date,
    )
    for tag_name in tags:
        from apps.tags.models import Tag
        tag, _ = Tag.objects.get_or_create(
            owner=webhook.user, name=str(tag_name)[:64]
        )
        task.tags.add(tag)

    webhook.last_used_at = timezone.now()
    webhook.save(update_fields=["last_used_at"])
    return Response({"id": task.id}, status=status.HTTP_201_CREATED)


