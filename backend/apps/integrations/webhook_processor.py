"""Procesador de webhooks con idempotencia, reintentos y DLQ."""
import logging
from datetime import timedelta
from django.utils import timezone

from .models import WebhookDelivery, GitHubRepo, GitHubIssueLink
from apps.tasks.models import Task

logger = logging.getLogger(__name__)

# Tiempo de espera entre reintentos (creciente)
RETRY_DELAYS = [60, 120, 300, 600, 1800]  # 1m, 2m, 5m, 10m, 30m


def process_webhook_delivery(delivery_id, event_type, action, payload, repo_full_name=""):
    """Procesa una entrega de webhook con idempotencia.

    Retorna (response_data, status_code).
    Si ya fue procesado, retorna 200 sin reprocesar.
    """
    # Idempotencia: buscar o crear el registro
    delivery, created = WebhookDelivery.objects.get_or_create(
        delivery_id=delivery_id,
        defaults={
            "event_type": event_type,
            "action": action,
            "payload": payload,
            "repo_full_name": repo_full_name,
        },
    )

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
        logger.error(f"Error procesando webhook {delivery_id}: {e}")
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
            "error": f"Error procesando webhook: {str(e)}",
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
    return {"message": f"Event {event_type}/{action} no handler"}


def _handle_issue_event(action, issue_data, repo_full_name=None):
    """Maneja eventos de issues."""
    from .sync_service import sync_issue_to_task, import_issue_as_task

    issue = issue_data.get("issue", {})
    repo_info = issue_data.get("repository", {})
    repo_full_name = repo_full_name or repo_info.get("full_name", "")
    issue_number = issue.get("number")

    if not issue_number or not repo_full_name:
        return {"message": "Missing issue data"}

    repo = GitHubRepo.objects.filter(full_name=repo_full_name).first()
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
        for r in repos_removed:
            GitHubRepo.objects.filter(repo_id=r["id"]).delete()

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
    """Maneja eventos de pull requests (registro para futura trazabilidad)."""
    pr = payload.get("pull_request", {})
    repo_info = payload.get("repository", {})
    return {
        "message": f"PR #{pr.get('number')} {action} en {repo_info.get('full_name')}",
        "pr_state": pr.get("state"),
        "pr_merged": pr.get("merged", False),
    }


def _handle_release_event(action, payload):
    """Maneja eventos de releases."""
    release = payload.get("release", {})
    repo_info = payload.get("repository", {})
    return {
        "message": f"Release {release.get('tag_name')} {action} en {repo_info.get('full_name')}",
    }


def retry_dead_letter_deliveries():
    """Reintenta manualmente las entregas en DLQ. Ejecutado por admin o comando."""
    dead = WebhookDelivery.objects.filter(status=WebhookDelivery.Status.DEAD_LETTER)
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
