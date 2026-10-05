"""Servicio de sincronización bidireccional entre tareas e issues de GitHub."""
from django.utils import timezone

from apps.tasks.models import Task

from .github_client import GitHubAppClient
from .models import GitHubIssueLink

# Mapeo de estados: tarea local ↔ issue de GitHub
TASK_TO_ISSUE_STATE = {
    Task.State.COMPLETED: "closed",
    Task.State.CANCELLED: "closed",
    Task.State.ARCHIVED: "closed",
}
ISSUE_TO_TASK_STATE = {
    "open": Task.State.PENDING,
    "closed": Task.State.COMPLETED,
}


def sync_task_to_issue(task):
    """Crea o actualiza un issue de GitHub cuando una tarea cambia localmente.
    Si la tarea no tiene link, no hace nada (se crea el link explícitamente).
    """
    link = getattr(task, "github_link", None)
    if not link:
        return None

    client = GitHubAppClient(
        installation_id=link.repo.installation.installation_id
    )
    owner, repo_name = link.repo.owner, link.repo.name

    # Determinar el estado del issue
    issue_state = TASK_TO_ISSUE_STATE.get(task.state, "open")

    # Construir el body del issue con metadatos
    body_parts = [task.description or ""]
    body_parts.append("\n---\n_Synced from TODOlist_")
    if task.due_date:
        body_parts.append(f"_Due: {task.due_date.strftime('%Y-%m-%d')}_")
    if task.priority is not None:
        body_parts.append(f"_Priority: P{task.priority}_")
    body = "\n".join(body_parts)

    updated = client.update_issue(
        owner=owner,
        repo=repo_name,
        issue_number=link.issue_number,
        state=issue_state,
        title=task.title,
        body=body,
    )

    link.issue_state = updated.get("state", issue_state)
    link.last_synced_at = timezone.now()
    link.save(update_fields=["issue_state", "last_synced_at", "updated_at"])
    return link


def sync_issue_to_task(link, issue_data):
    """Actualiza una tarea local cuando un issue cambia en GitHub.

    Descarta eventos stale: si el payload es más viejo que el último
    sync conocido del link, no sobrescribe la tarea local.
    """
    from django.utils.dateparse import parse_datetime

    task = link.task
    # Marcar para evitar recursión: el signal no debe sync de vuelta
    task._syncing_from_github = True

    # Ordenamiento temporal: ignorar eventos más viejos que el último sync
    gh_updated = issue_data.get("updated_at")
    if gh_updated:
        gh_dt = parse_datetime(gh_updated)
        if gh_dt and link.last_synced_at and gh_dt < link.last_synced_at:
            return task

    # Actualizar título y descripción
    if issue_data.get("title") and issue_data["title"] != task.title:
        task.title = issue_data["title"][:255]

    # Actualizar estado
    gh_state = issue_data.get("state", "open")
    new_state = ISSUE_TO_TASK_STATE.get(gh_state, task.state)
    task.state = new_state
    task.save()
    from apps.tasks.services import apply_completion_effects
    apply_completion_effects(task)

    link.issue_state = gh_state
    link.issue_url = issue_data.get("html_url", link.issue_url)
    link.last_synced_at = timezone.now()
    link.save(update_fields=["issue_state", "issue_url", "last_synced_at", "updated_at"])
    return task


def create_issue_for_task(task, repo):
    """Crea un issue en GitHub y lo vincula a la tarea."""
    client = GitHubAppClient(installation_id=repo.installation.installation_id)

    body_parts = [task.description or ""]
    body_parts.append("\n---\n_Synced from TODOlist_")
    if task.due_date:
        body_parts.append(f"_Due: {task.due_date.strftime('%Y-%m-%d')}_")
    body = "\n".join(body_parts)

    issue = client.create_issue(
        owner=repo.owner,
        repo=repo.name,
        title=task.title,
        body=body,
    )

    link = GitHubIssueLink.objects.create(
        task=task,
        repo=repo,
        issue_number=issue["number"],
        issue_id=issue["id"],
        issue_url=issue["html_url"],
        issue_state=issue["state"],
        last_synced_at=timezone.now(),
    )
    return link


def import_issue_as_task(issue_data, repo, user):
    """Importa un issue de GitHub como una nueva tarea local."""
    # Extraer número y datos
    issue_number = issue_data["number"]
    issue_id = issue_data["id"]
    title = issue_data["title"][:255]
    body = issue_data.get("body", "") or ""
    state = issue_data.get("state", "open")

    # No duplicar si ya existe el link
    existing = GitHubIssueLink.objects.filter(
        repo=repo, issue_number=issue_number
    ).first()
    if existing:
        return existing.task, False  # ya existía

    task_state = ISSUE_TO_TASK_STATE.get(state, Task.State.PENDING)
    from apps.tasks.services import next_position_seq
    pos, _seq = next_position_seq(user)
    task = Task.objects.create(
        owner=user,
        title=title,
        description=body[:2000],
        state=task_state,
        position=pos,
    )

    GitHubIssueLink.objects.create(
        task=task,
        repo=repo,
        issue_number=issue_number,
        issue_id=issue_id,
        issue_url=issue_data.get("html_url", ""),
        issue_state=state,
        last_synced_at=timezone.now(),
    )
    return task, True  # nueva


def sync_repo_issues(repo):
    """Sincroniza todos los issues de un repo: trae cambios de GitHub → local."""
    client = GitHubAppClient(installation_id=repo.installation.installation_id)
    issues = client.list_issues(repo.owner, repo.name, state="all", per_page=100)

    synced = 0
    for issue_data in issues:
        # Ignorar pull requests (vienen en la API de issues)
        if "pull_request" in issue_data:
            continue
        link = GitHubIssueLink.objects.filter(
            repo=repo, issue_number=issue_data["number"]
        ).first()
        if link:
            sync_issue_to_task(link, issue_data)
            synced += 1
    return synced
