"""URLs de la API de integraciones."""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    GitHubInstallationViewSet,
    GitHubRepoViewSet,
    GitHubIssueLinkViewSet,
    GitHubPullRequestViewSet,
    GitHubCommitViewSet,
    GitHubReleaseViewSet,
    GitHubCheckRunViewSet,
    github_oauth_start,
    github_oauth_callback,
    github_webhook,
    webhook_deliveries,
    webhook_retry_dead_letter,
    oauth_providers,
)

router = DefaultRouter()
router.register(
    r"github/installations", GitHubInstallationViewSet, basename="github-installation"
)
router.register(r"github/repos", GitHubRepoViewSet, basename="github-repo")
router.register(r"github/links", GitHubIssueLinkViewSet, basename="github-link")
router.register(r"github/prs", GitHubPullRequestViewSet, basename="github-pr")
router.register(r"github/commits", GitHubCommitViewSet, basename="github-commit")
router.register(r"github/releases", GitHubReleaseViewSet, basename="github-release")
router.register(r"github/checks", GitHubCheckRunViewSet, basename="github-check")

urlpatterns = [
    path("auth/github/start/", github_oauth_start, name="github_oauth_start"),
    path("auth/oauth-providers/", oauth_providers, name="oauth_providers"),
    path("auth/github/callback/", github_oauth_callback, name="github_oauth_callback"),
    path("webhooks/github/", github_webhook, name="github_webhook"),
    path("webhooks/deliveries/", webhook_deliveries, name="webhook_deliveries"),
    path("webhooks/retry-dead-letter/", webhook_retry_dead_letter, name="webhook_retry_dead_letter"),
    path("", include(router.urls)),
]
