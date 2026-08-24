"""Tareas de Celery para sincronización periódica con GitHub."""
import logging

from celery import shared_task

from .models import GitHubRepo
from .sync_service import sync_repo_issues

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def sync_repo_issues_task(self, repo_id):
    """Sincroniza los issues de un repo específico."""
    try:
        repo = GitHubRepo.objects.get(id=repo_id)
        if not repo.sync_enabled:
            return f"Repo {repo.full_name} sync disabled"
        synced = sync_repo_issues(repo)
        return f"Synced {synced} issues from {repo.full_name}"
    except GitHubRepo.DoesNotExist:
        return f"Repo {repo_id} not found"
    except Exception as e:
        logger.error(f"Error syncing repo {repo_id}: {e}")
        raise self.retry(exc=e, countdown=60)


@shared_task
def sync_all_github_issues():
    """Sincroniza todos los repos con sync habilitado. Ejecutada por Celery beat."""
    repos = GitHubRepo.objects.filter(sync_enabled=True)
    total = 0
    for repo in repos:
        sync_repo_issues_task.delay(repo.id)
        total += 1
    return f"Queued sync for {total} repos"
