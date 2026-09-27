"""URLs de la API de integraciones."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    GitHubCheckRunViewSet,
    GitHubCommitViewSet,
    GitHubInstallationViewSet,
    GitHubIssueLinkViewSet,
    GitHubPullRequestViewSet,
    GitHubReleaseViewSet,
    GitHubRepoViewSet,
    InboundWebhookViewSet,
    dora_metrics,
    github_oauth_callback,
    github_oauth_start,
    github_webhook,
    inbound_webhook,
    oauth_providers,
    webhook_deliveries,
    webhook_retry_dead_letter,
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
router.register(
    r"inbound-webhooks", InboundWebhookViewSet, basename="inbound-webhook"
)

urlpatterns = [
    path("inbound/<str:token>/", inbound_webhook, name="inbound_webhook"),
    path("auth/github/start/", github_oauth_start, name="github_oauth_start"),
    path("auth/oauth-providers/", oauth_providers, name="oauth_providers"),
    path("auth/github/callback/", github_oauth_callback, name="github_oauth_callback"),
    path("webhooks/github/", github_webhook, name="github_webhook"),
    path("webhooks/deliveries/", webhook_deliveries, name="webhook_deliveries"),
    path("webhooks/retry-dead-letter/", webhook_retry_dead_letter, name="webhook_retry_dead_letter"),
    path("metrics/dora/", dora_metrics, name="dora_metrics"),
    path("", include(router.urls)),
]
