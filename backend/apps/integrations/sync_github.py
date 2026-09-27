"""Sincronización activa de PRs, commits, releases y check runs desde GitHub.

A diferencia de los webhooks (pasivos), estas funciones consultan la API de
GitHub de forma proactiva para mantener la BD actualizada aunque se pierdan
eventos. Cada función es idempotente (usa ``update_or_create``) y robusta
frente a rate limits y errores de red.
"""
import logging
import re

import requests

from .exceptions import IntegrationError
from .github_client import GitHubAppClient
from .models import (
    GitHubCheckRun,
    GitHubCommit,
    GitHubIssueLink,
    GitHubPullRequest,
    GitHubRelease,
)

logger = logging.getLogger(__name__)

# Número de elementos a traer por página en cada sincronización
PR_PER_PAGE = 100
COMMIT_PER_PAGE = 30
RELEASE_PER_PAGE = 30
CHECK_RUN_PER_PAGE = 30


def _get_client(installation):
    """Construye un GitHubAppClient para la instalación dada."""
    return GitHubAppClient(installation_id=installation.installation_id)


def _parse_iso(value):
    """Convierte un timestamp ISO 8601 de GitHub a objeto, o None."""
    if not value:
        return None
    try:
        from django.utils.dateparse import parse_datetime

        return parse_datetime(value.replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001  # boundary intencional: fallo externo no rompe el flujo
        return None


def sync_pull_requests(repo, installation):
    """Sincroniza PRs abiertos y cerrados recientes de un repo.

    Trae los PRs abiertos y los cerrados más recientes (ordenados por
    actualización) y los crea/actualiza en la BD usando ``update_or_create``
    con ``github_id`` (``pr_id``) como clave.
    """
    client = _get_client(installation)
    synced = 0
    seen_ids = set()

    for state in ("open", "closed"):
        try:
            prs = client.list_pull_requests(
                repo.owner, repo.name, state=state, per_page=PR_PER_PAGE
            )
        except (IntegrationError, requests.RequestException) as e:
            logger.warning(
                "sync_pull_requests: error listando PRs %s state=%s: %s",
                repo.full_name, state, e,
            )
            continue

        for pr_data in prs:
            pr_id = pr_data.get("id")
            if not pr_id or pr_id in seen_ids:
                continue
            seen_ids.add(pr_id)

            pr_number = pr_data.get("number")
            try:
                GitHubPullRequest.objects.update_or_create(
                    repo=repo, pr_number=pr_number,
                    defaults={
                        "pr_id": pr_id,
                        "title": (pr_data.get("title") or "")[:500],
                        "state": pr_data.get("state", "open"),
                        "is_merged": pr_data.get("merged", False),
                        "is_draft": pr_data.get("draft", False),
                        "html_url": pr_data.get("html_url", ""),
                        "head_branch": (pr_data.get("head") or {}).get("ref", ""),
                        "base_branch": (pr_data.get("base") or {}).get("ref", ""),
                        "author": (pr_data.get("user") or {}).get("login", ""),
                        "created_at_gh": _parse_iso(pr_data.get("created_at")),
                        "merged_at": _parse_iso(pr_data.get("merged_at")),
                        "closed_at": _parse_iso(pr_data.get("closed_at")),
                        "review_comments_count": pr_data.get("review_comments", 0),
                    },
                )
                synced += 1

                # Vincular tareas referenciadas por #number en body/title
                text = (pr_data.get("body") or "") + " " + (pr_data.get("title") or "")
                issue_refs = {int(m) for m in re.findall(r"#(\d+)", text)}
                if issue_refs:
                    pr_obj = GitHubPullRequest.objects.get(
                        repo=repo, pr_number=pr_number
                    )
                    for issue_num in issue_refs:
                        link = GitHubIssueLink.objects.filter(
                            repo=repo, issue_number=issue_num
                        ).first()
                        if link:
                            pr_obj.tasks.add(link.task)
            except Exception as e:  # noqa: BLE001  # boundary intencional: fallo externo no rompe el flujo
                logger.error(
                    "sync_pull_requests: error guardando PR #%s de %s: %s",
                    pr_number, repo.full_name, e,
                )

    logger.info("sync_pull_requests: %s PRs sincronizados para %s", synced, repo.full_name)
    return synced


def sync_commits(repo, installation):
    """Sincroniza los últimos commits de un repo (por defecto 30).

    Usa el SHA como clave única (``update_or_create`` por ``sha``).
    """
    client = _get_client(installation)
    synced = 0

    try:
        commits = client.list_commits(repo.owner, repo.name, per_page=COMMIT_PER_PAGE)
    except (IntegrationError, requests.RequestException) as e:
        logger.warning("sync_commits: error listando commits %s: %s", repo.full_name, e)
        return 0

    for c in commits:
        sha = c.get("sha")
        if not sha:
            continue
        commit_info = c.get("commit", {}) or {}
        author_info = commit_info.get("author", {}) or {}

        try:
            GitHubCommit.objects.update_or_create(
                sha=sha,
                defaults={
                    "repo": repo,
                    "message": commit_info.get("message", ""),
                    "author": author_info.get("name", "") or (c.get("author") or {}).get("login", ""),
                    "author_date": _parse_iso(author_info.get("date")),
                    "html_url": c.get("html_url", ""),
                },
            )
            synced += 1
        except Exception as e:  # noqa: BLE001  # boundary intencional: fallo externo no rompe el flujo
            logger.error(
                "sync_commits: error guardando commit %s de %s: %s",
                (sha or "")[:8], repo.full_name, e,
            )

    logger.info("sync_commits: %s commits sincronizados para %s", synced, repo.full_name)
    return synced


def sync_releases(repo, installation):
    """Sincroniza releases de un repo vía GitHub API.

    Usa ``release_id`` como clave única (``update_or_create``).
    """
    client = _get_client(installation)
    synced = 0

    try:
        releases = client.list_releases(repo.owner, repo.name, per_page=RELEASE_PER_PAGE)
    except (IntegrationError, requests.RequestException) as e:
        logger.warning("sync_releases: error listando releases %s: %s", repo.full_name, e)
        return 0

    for r in releases:
        release_id = r.get("id")
        if not release_id:
            continue
        try:
            GitHubRelease.objects.update_or_create(
                release_id=release_id,
                defaults={
                    "repo": repo,
                    "tag_name": r.get("tag_name", ""),
                    "name": (r.get("name") or "")[:500],
                    "body": r.get("body") or "",
                    "html_url": r.get("html_url", ""),
                    "state": "prerelease" if r.get("prerelease") else "published",
                    "is_prerelease": r.get("prerelease", False),
                    "author": (r.get("author") or {}).get("login", ""),
                    "published_at": _parse_iso(r.get("published_at")),
                },
            )
            synced += 1
        except Exception as e:  # noqa: BLE001  # boundary intencional: fallo externo no rompe el flujo
            logger.error(
                "sync_releases: error guardando release %s de %s: %s",
                r.get("tag_name"), repo.full_name, e,
            )

    logger.info("sync_releases: %s releases sincronizados para %s", synced, repo.full_name)
    return synced


def sync_check_runs(repo, installation):
    """Sincroniza check runs recientes de un repo (rama por defecto).

    Usa ``check_id`` como clave única (``update_or_create``).
    """
    client = _get_client(installation)
    synced = 0

    try:
        checks = client.list_check_runs(
            repo.owner, repo.name, ref=repo.default_branch, per_page=CHECK_RUN_PER_PAGE
        )
    except (IntegrationError, requests.RequestException) as e:
        logger.warning("sync_check_runs: error listando checks %s: %s", repo.full_name, e)
        return 0

    for ch in checks:
        check_id = ch.get("id")
        if not check_id:
            continue
        try:
            check, _ = GitHubCheckRun.objects.update_or_create(
                check_id=check_id,
                defaults={
                    "repo": repo,
                    "name": (ch.get("name") or "")[:255],
                    "status": ch.get("status", "queued"),
                    "conclusion": ch.get("conclusion") or "",
                    "html_url": ch.get("html_url", ""),
                    "started_at": _parse_iso(ch.get("started_at")),
                    "completed_at": _parse_iso(ch.get("completed_at")),
                    "commit_sha": ch.get("head_sha", ""),
                },
            )
            synced += 1

            # Asociar al PR si el check lo referencia
            pr_data = ch.get("pull_requests") or []
            if pr_data:
                pr_number = pr_data[0].get("number")
                pr = GitHubPullRequest.objects.filter(
                    repo=repo, pr_number=pr_number
                ).first()
                if pr:
                    check.pull_request = pr
                    check.save(update_fields=["pull_request"])
                    conclusion = ch.get("conclusion") or ""
                    pr.ci_status = conclusion or ch.get("status", "")
                    pr.ci_url = ch.get("html_url", "")
                    pr.save(update_fields=["ci_status", "ci_url"])
        except Exception as e:  # noqa: BLE001  # boundary intencional: fallo externo no rompe el flujo
            logger.error(
                "sync_check_runs: error guardando check %s de %s: %s",
                check_id, repo.full_name, e,
            )

    logger.info("sync_check_runs: %s checks sincronizados para %s", synced, repo.full_name)
    return synced


def sync_repo_data(repo):
    """Sincroniza PRs, commits, releases y check runs de un repo.

    Retorna un dict con los conteos de cada tipo. Es robusto: un error en
    una sección no detiene las demás.
    """
    installation = repo.installation
    result = {
        "pull_requests": 0,
        "commits": 0,
        "releases": 0,
        "check_runs": 0,
    }

    if not repo.sync_enabled:
        logger.info("sync_repo_data: sync deshabilitada para %s", repo.full_name)
        return result

    try:
        result["pull_requests"] = sync_pull_requests(repo, installation)
    except Exception:
        logger.exception("sync_repo_data: error PRs %s", repo.full_name)

    try:
        result["commits"] = sync_commits(repo, installation)
    except Exception:
        logger.exception("sync_repo_data: error commits %s", repo.full_name)

    try:
        result["releases"] = sync_releases(repo, installation)
    except Exception:
        logger.exception("sync_repo_data: error releases %s", repo.full_name)

    try:
        result["check_runs"] = sync_check_runs(repo, installation)
    except Exception:
        logger.exception("sync_repo_data: error check_runs %s", repo.full_name)

    return result
