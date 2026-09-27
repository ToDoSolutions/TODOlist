"""Métricas Prometheus para monitoreo de la aplicación."""
from django.http import HttpResponse
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# Contadores
REQUEST_COUNT = Counter(
    "todolist_requests_total",
    "Total requests by method and endpoint",
    ["method", "endpoint", "status"],
)

TASKS_CREATED = Counter(
    "todolist_tasks_created_total",
    "Total tasks created",
)

TASKS_COMPLETED = Counter(
    "todolist_tasks_completed_total",
    "Total tasks completed",
)

API_CALLS = Counter(
    "todolist_api_calls_total",
    "API calls by endpoint",
    ["endpoint", "method"],
)

# Métricas de negocio
AUTOMATION_EXECUTIONS = Counter(
    "todolist_automation_executions_total",
    "Automation rule executions",
    ["status"],
)

SYNC_CONFLICTS = Counter(
    "todolist_sync_conflicts_total",
    "Offline sync conflicts detected",
    ["resolution"],
)

WEBHOOK_DELIVERIES = Counter(
    "todolist_webhook_deliveries_total",
    "GitHub webhook deliveries processed",
    ["status"],
)

# Histogramas (latencia)
REQUEST_LATENCY = Histogram(
    "todolist_request_latency_seconds",
    "Request latency in seconds",
    ["endpoint"],
)

DB_QUERY_TIME = Histogram(
    "todolist_db_query_seconds",
    "Database query time in seconds",
)

TASK_LEAD_TIME = Histogram(
    "todolist_task_lead_time_seconds",
    "Task lead time (created → completed) in seconds",
    buckets=(3600, 86400, 259200, 604800, 2592000, 7776000, float("inf")),
)

# Gauges (valores actuales)
ACTIVE_USERS = Gauge(
    "todolist_active_users",
    "Currently active users",
)

OPEN_TASKS = Gauge(
    "todolist_open_tasks",
    "Currently open tasks",
)

ACTIVE_SPRINTS = Gauge(
    "todolist_active_sprints",
    "Currently active sprints",
)


def metrics_view(request):
    """Endpoint de métricas Prometheus — restringido a admins o token Bearer.

    Prometheus puede scrapear con Authorization: Bearer $METRICS_TOKEN
    (configurable por env). En su defecto solo staff autenticado.
    """
    from django.conf import settings as _settings
    from django.http import HttpResponseForbidden

    token = getattr(_settings, "METRICS_TOKEN", "") or ""
    auth = request.META.get("HTTP_AUTHORIZATION", "")
    import secrets as _secrets
    if token and _secrets.compare_digest(auth, f"Bearer {token}"):
        return HttpResponse(generate_latest(), content_type=CONTENT_TYPE_LATEST)
    user = getattr(request, "user", None)
    if user and user.is_authenticated and user.is_staff:
        return HttpResponse(generate_latest(), content_type=CONTENT_TYPE_LATEST)
    return HttpResponseForbidden("Forbidden")
