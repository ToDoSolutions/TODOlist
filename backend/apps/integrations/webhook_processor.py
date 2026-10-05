"""Procesador de webhooks con idempotencia, reintentos y DLQ."""
import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import GitHubIssueLink, GitHubRepo, WebhookDelivery

logger = logging.getLogger(__name__)

# Tiempo de espera entre reintentos (creciente)
RETRY_DELAYS = [60, 120, 300, 600, 1800]  # 1m, 2m, 5m, 10m, 30m


def process_webhook_delivery(delivery_id, event_type, action, payload, repo_full_name=""):
    """Procesa una entrega de webhook con idempotencia.

    Retorna (response_data, status_code).
    Si ya fue procesado, retorna 200 sin reprocesar.
    El row-lock evita que dos entregas concurrentes con el mismo
    delivery_id se procesen dos veces.
    """
    with transaction.atomic():
        # Idempotencia: buscar o crear el registro
        delivery, _created = WebhookDelivery.objects.get_or_create(
            delivery_id=delivery_id,
            defaults={
                "event_type": event_type,
                "action": action,
                "payload": payload,
                "repo_full_name": repo_full_name,
            },
        )

        # Lock de fila: serializa procesamiento concurrente del mismo id
        delivery = WebhookDelivery.objects.select_for_update().get(pk=delivery.pk)

        # Si ya fue procesado, no hacer nada (idempotencia)
        if delivery.status == WebhookDelivery.Status.PROCESSED:
            return {"message": f"Webhook {delivery_id} ya procesado"}, 200

        if delivery.status == WebhookDelivery.Status.DEAD_LETTER:
            return {"message": f"Webhook {delivery_id} en DLQ, no se reprocesa"}, 200

        # Procesar
        try:
            result = _dispatch_event(event_type, action, payload)
            delivery.status = WebhookDelivery.Status.PROCESSED
            delivery.processed_at = timezone.now()
            delivery.save(update_fields=["status", "processed_at"])
            return result, 200
        except Exception as e:
            logger.exception(f"Error procesando webhook {delivery_id}")
            delivery.error_message = str(e)[:500]
            delivery.retry_count += 1

            if delivery.retry_count >= delivery.max_retries:
                delivery.status = WebhookDelivery.Status.DEAD_LETTER
                delivery.next_retry_at = None
            else:
                delivery.status = WebhookDelivery.Status.RETRYING
                delay = RETRY_DELAYS[min(delivery.retry_count - 1, len(RETRY_DELAYS) - 1)]
                delivery.next_retry_at = timezone.now() + timedelta(seconds=delay)

            delivery.save(update_fields=["status", "error_message", "retry_count", "next_retry_at"])

            return {
                "error": "Error procesando webhook",
                "retry_count": delivery.retry_count,
                "next_retry_at": delivery.next_retry_at.isoformat() if delivery.next_retry_at else None,
            }, 500


def _dispatch_event(event_type, action, payload):
    """Despacha el evento al handler correspondiente."""
    if event_type == "issues":
        return _handle_issue_event(action, payload)
    elif event_type == "installation_repositories":
        return _handle_installation_repos_event(action, payload)
    elif event_type == "installation":
        return _handle_installation_event(action, payload)
    elif event_type == "pull_request":
        return _handle_pr_event(action, payload)
    elif event_type == "release":
        return _handle_release_event(action, payload)
    elif event_type == "check_run":
        return _handle_check_run_event(action, payload)
    return {"message": f"Event {event_type}/{action} no handler"}


def _resolve_repo(payload, repo_full_name=""):
    """Resuelve el GitHubRepo scopeado por instalación del propio evento.

    ``full_name`` no es único global (varios usuarios pueden registrar el
    mismo repo de org), así que se resuelve por ``(installation_id,
    repo_id)`` del payload. Fallback a ``full_name`` + instalación y, como
    último recurso (payloads sin installation), full_name solo.
    """
    repo_info = payload.get("repository", {})
    installation_id = payload.get("installation", {}).get("id")
    repo_id = repo_info.get("id")
    full_name = repo_full_name or repo_info.get("full_name", "")

    if installation_id:
        if repo_id:
            repo = GitHubRepo.objects.filter(
                installation__installation_id=installation_id, repo_id=repo_id
            ).first()
            if repo:
                return repo
        if full_name:
            repo = GitHubRepo.objects.filter(
                installation__installation_id=installation_id, full_name=full_name
            ).first()
            if repo:
                return repo
            return None
        return None

    if not full_name:
        return None
    logger.warning(
        "Webhook sin installation.id: resolviendo repo por full_name=%s (ambiguo)", full_name
    )
    return GitHubRepo.objects.filter(full_name=full_name).first()


def _handle_issue_event(action, issue_data, repo_full_name=None):
    """Maneja eventos de issues."""
    from .sync_service import import_issue_as_task, sync_issue_to_task

    issue = issue_data.get("issue", {})
    repo_info = issue_data.get("repository", {})
    repo_full_name = repo_full_name or repo_info.get("full_name", "")
    issue_number = issue.get("number")

    if not issue_number or not repo_full_name:
        return {"message": "Missing issue data"}

    repo = _resolve_repo(issue_data, repo_full_name)
    if not repo:
        return {"message": f"Repo {repo_full_name} not tracked"}

    link = GitHubIssueLink.objects.filter(repo=repo, issue_number=issue_number).first()

    if action == "opened" and not link:
        installation = repo.installation
        import_issue_as_task(issue, repo, installation.user)
        return {"message": f"Issue #{issue_number} imported"}

    if link and action in ("opened", "closed", "reopened", "edited", "labeled", "unlabeled", "assigned", "unassigned"):
        link.task._syncing_from_github = True
        sync_issue_to_task(link, issue)
        return {"message": f"Issue #{issue_number} synced ({action})"}

    return {"message": f"Action {action} no handler for issue #{issue_number}"}


def _handle_installation_repos_event(action, payload):
    """Maneja eventos de instalación (repos añadidos/eliminados)."""
    from .models import GitHubInstallation

    repos_added = payload.get("repositories_added", [])
    repos_removed = payload.get("repositories_removed", [])
    installation_id = payload.get("installation", {}).get("id")

    if action == "added":
        for r in repos_added:
            inst = GitHubInstallation.objects.filter(installation_id=installation_id).first()
            if inst:
                GitHubRepo.objects.get_or_create(
                    installation=inst,
                    repo_id=r["id"],
                    defaults={
                        "full_name": r["full_name"],
                        "name": r["name"],
                        "owner": r["full_name"].split("/")[0],
                    },
                )
    elif action == "removed":
        # Scopear por instalación: repo_id es global, pero un `removed` solo
        # debe borrar el tracking de la instalación que emite el evento.
        inst = GitHubInstallation.objects.filter(installation_id=installation_id).first()
        for r in repos_removed:
            qs = GitHubRepo.objects.filter(repo_id=r["id"])
            if inst:
                qs = qs.filter(installation=inst)
            elif installation_id:
                # Instalación desconocida: no borrar nada de otros tenants.
                continue
            qs.delete()

    return {"message": f"Installation repos {action}"}


def _handle_installation_event(action, payload):
    """Maneja eventos de instalación/desinstalación de la GitHub App."""
    from .models import GitHubInstallation

    installation = payload.get("installation", {})
    installation_id = installation.get("id")

    if action == "deleted":
        GitHubInstallation.objects.filter(installation_id=installation_id).delete()

    return {"message": f"Installation {action}"}


def _handle_pr_event(action, payload):
    """Maneja eventos de pull requests: crea/actualiza el PR en la BD."""

    from .models import GitHubPullRequest, GitHubRepo

    pr_data = payload.get("pull_request", {})
    repo_info = payload.get("repository", {})
    repo_full_name = repo_info.get("full_name", "")
    pr_number = pr_data.get("number")

    if not pr_number or not repo_full_name:
        return {"message": "Missing PR data"}

    repo = _resolve_repo(payload, repo_full_name)
    if not repo:
        return {"message": f"Repo {repo_full_name} not tracked"}

    pr, created = GitHubPullRequest.objects.update_or_create(
        repo=repo, pr_number=pr_number,
        defaults={
            "pr_id": pr_data.get("id", 0),
            "title": pr_data.get("title", "")[:500],
            "state": pr_data.get("state", "open"),
            "is_merged": pr_data.get("merged", False),
            "is_draft": pr_data.get("draft", False),
            "html_url": pr_data.get("html_url", ""),
            "head_branch": pr_data.get("head", {}).get("ref", ""),
            "base_branch": pr_data.get("base", {}).get("ref", ""),
            "author": pr_data.get("user", {}).get("login", ""),
            "created_at_gh": pr_data.get("created_at"),
            "merged_at": pr_data.get("merged_at"),
            "closed_at": pr_data.get("closed_at"),
            "review_comments_count": pr_data.get("review_comments", 0),
        },
    )

    # Detectar tareas referenciadas por #number en el body/title
    import re
    text = (pr_data.get("body") or "") + " " + pr_data.get("title", "")
    issue_refs = {int(m) for m in re.findall(r"#(\d+)", text)}
    if issue_refs:
        from .models import GitHubIssueLink
        for issue_num in issue_refs:
            link = GitHubIssueLink.objects.filter(
                repo=repo, issue_number=issue_num
            ).first()
            if link:
                pr.tasks.add(link.task)

    return {
        "message": f"PR #{pr_number} {action} en {repo_full_name}",
        "pr_state": pr_data.get("state"),
        "pr_merged": pr_data.get("merged", False),
        "created": created,
    }


def _handle_release_event(action, payload):
    """Maneja eventos de releases: crea/actualiza el release en la BD."""
    from .models import GitHubRelease, GitHubRepo

    release_data = payload.get("release", {})
    repo_info = payload.get("repository", {})
    repo_full_name = repo_info.get("full_name", "")
    tag = release_data.get("tag_name", "")

    if not tag or not repo_full_name:
        return {"message": "Missing release data"}

    repo = _resolve_repo(payload, repo_full_name)
    if not repo:
        return {"message": f"Repo {repo_full_name} not tracked"}

    _release, created = GitHubRelease.objects.update_or_create(
        release_id=release_data.get("id", 0),
        defaults={
            "repo": repo,
            "tag_name": tag,
            "name": (release_data.get("name") or "")[:500],
            "body": release_data.get("body") or "",
            "html_url": release_data.get("html_url", ""),
            "state": "prerelease" if release_data.get("prerelease") else "published",
            "is_prerelease": release_data.get("prerelease", False),
            "author": release_data.get("author", {}).get("login", ""),
            "published_at": release_data.get("published_at"),
        },
    )

    return {
        "message": f"Release {tag} {action} en {repo_full_name}",
        "created": created,
    }


def _handle_check_run_event(action, payload):
    """Maneja eventos de check_run (CI/CD)."""
    from .models import GitHubCheckRun, GitHubPullRequest, GitHubRepo

    check_data = payload.get("check_run", {})
    repo_info = payload.get("repository", {})
    repo_full_name = repo_info.get("full_name", "")

    if not repo_full_name:
        return {"message": "Missing repo data"}

    repo = _resolve_repo(payload, repo_full_name)
    if not repo:
        return {"message": f"Repo {repo_full_name} not tracked"}

    check, created = GitHubCheckRun.objects.update_or_create(
        check_id=check_data.get("id", 0),
        defaults={
            "repo": repo,
            "name": check_data.get("name", "")[:255],
            "status": check_data.get("status", "queued"),
            "conclusion": check_data.get("conclusion") or "",
            "html_url": check_data.get("html_url", ""),
            "started_at": check_data.get("started_at"),
            "completed_at": check_data.get("completed_at"),
            "commit_sha": check_data.get("head_sha", ""),
        },
    )

    # Actualizar el CI status del PR si existe
    pr_data = check_data.get("pull_requests", [])
    if pr_data:
        pr_number = pr_data[0].get("number")
        pr = GitHubPullRequest.objects.filter(repo=repo, pr_number=pr_number).first()
        if pr:
            check.pull_request = pr
            check.save(update_fields=["pull_request"])
            # Actualizar CI status del PR
            conclusion = check_data.get("conclusion") or ""
            pr.ci_status = conclusion or check_data.get("status", "")
            pr.ci_url = check_data.get("html_url", "")
            pr.save(update_fields=["ci_status", "ci_url"])

    return {
        "message": f"Check {check_data.get('name')} {check_data.get('status')} en {repo_full_name}",
        "created": created,
    }


def retry_dead_letter_deliveries(repo_full_name=None, repo_full_name__in=None):
    """Reintenta manualmente las entregas en DLQ. Ejecutado por admin o comando.

    Si se pasa ``repo_full_name``, solo reintenta entregas de ese repo.
    Si se pasa ``repo_full_name__in``, solo reintenta entregas de esos repos.
    """
    dead = WebhookDelivery.objects.filter(status=WebhookDelivery.Status.DEAD_LETTER)
    if repo_full_name:
        dead = dead.filter(repo_full_name=repo_full_name)
    elif repo_full_name__in:
        dead = dead.filter(repo_full_name__in=repo_full_name__in)
    retried = 0
    for delivery in dead:
        delivery.status = WebhookDelivery.Status.PENDING
        delivery.retry_count = 0
        delivery.error_message = ""
        delivery.save(update_fields=["status", "retry_count", "error_message"])
        # Encolar reprocesamiento asíncrono
        from .tasks import process_webhook_retry_task
        process_webhook_retry_task.delay(delivery.id)
        retried += 1
    return f"Reintentando {retried} entregas de DLQ"


def process_pending_retries():
    """Procesa entregas pendientes de reintento cuyo next_retry_at ya pasó."""
    now = timezone.now()
    pending = WebhookDelivery.objects.filter(
        status=WebhookDelivery.Status.RETRYING,
        next_retry_at__lte=now,
    )
    processed = 0
    for delivery in pending:
        from .tasks import process_webhook_retry_task
        process_webhook_retry_task.delay(delivery.id)
        processed += 1
    return f"Encolados {processed} reintentos"
