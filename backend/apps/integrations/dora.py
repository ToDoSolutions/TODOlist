"""Métricas DORA (DevOps Research and Assessment).

Calculadas sobre los datos ya sincronizados de GitHub:
- Deployment Frequency: releases publicadas por semana.
- Lead Time for Changes: mediana de (merged_at - created_at_gh) de PRs.
- Change Failure Rate: % de check runs completados que fallaron.
- MTTR: media del tiempo entre un check run fallido y el siguiente éxito
  en el mismo repo (aproximación con los datos disponibles).
"""
from datetime import timedelta

from django.utils import timezone

from .models import (
    GitHubCheckRun,
    GitHubPullRequest,
    GitHubRelease,
    GitHubRepo,
)


def _median(values):
    if not values:
        return None
    s = sorted(values)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def get_dora_metrics(user, days=90):
    """Métricas DORA para los repos accesibles del usuario."""
    repos = GitHubRepo.objects.filter(installation__user=user)
    since = timezone.now() - timedelta(days=days)
    weeks = max(days / 7, 1)

    # Deployment Frequency: releases publicadas / semana
    releases = GitHubRelease.objects.filter(
        repo__in=repos,
        state=GitHubRelease.ReleaseState.PUBLISHED,
        published_at__gte=since,
    )
    deployment_frequency = round(releases.count() / weeks, 2)

    # Lead Time for Changes: mediana creación→merge de PRs
    merged_prs = GitHubPullRequest.objects.filter(
        repo__in=repos,
        is_merged=True,
        merged_at__gte=since,
        created_at_gh__isnull=False,
    )
    lead_times = [
        (pr.merged_at - pr.created_at_gh).total_seconds() / 3600
        for pr in merged_prs
        if pr.merged_at and pr.created_at_gh
    ]
    lead_time_hours = _median(lead_times)

    # Change Failure Rate: % check runs fallidos (de los completados)
    checks = GitHubCheckRun.objects.filter(
        repo__in=repos,
        status=GitHubCheckRun.CheckStatus.COMPLETED,
        started_at__gte=since,
    )
    completed = checks.count()
    failed = checks.filter(
        conclusion__in=[
            GitHubCheckRun.CheckConclusion.FAILURE,
            GitHubCheckRun.CheckConclusion.TIMED_OUT,
        ]
    ).count()
    change_failure_rate = round(failed / completed * 100, 1) if completed else 0.0

    # MTTR: media del gap fallo→éxito por repo
    recovery_times = []
    for repo in repos:
        ordered = list(
            GitHubCheckRun.objects.filter(
                repo=repo, status=GitHubCheckRun.CheckStatus.COMPLETED
            ).order_by("started_at").values_list("conclusion", "started_at")
        )
        for i, (conclusion, started) in enumerate(ordered):
            if conclusion not in (
                GitHubCheckRun.CheckConclusion.FAILURE,
                GitHubCheckRun.CheckConclusion.TIMED_OUT,
            ):
                continue
            for c2, s2 in ordered[i + 1:]:
                if c2 == GitHubCheckRun.CheckConclusion.SUCCESS and s2:
                    recovery_times.append((s2 - started).total_seconds() / 3600)
                    break
    mttr_hours = (
        round(sum(recovery_times) / len(recovery_times), 2)
        if recovery_times else None
    )

    return {
        "period_days": days,
        "deployment_frequency_per_week": deployment_frequency,
        "lead_time_for_changes_hours": (
            round(lead_time_hours, 2) if lead_time_hours is not None else None
        ),
        "change_failure_rate_pct": change_failure_rate,
        "mttr_hours": mttr_hours,
        "samples": {
            "releases": releases.count(),
            "merged_prs": len(lead_times),
            "check_runs": completed,
        },
    }
