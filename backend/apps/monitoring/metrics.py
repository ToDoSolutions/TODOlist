"""Métricas Prometheus para monitoreo de la aplicación."""
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from django.http import HttpResponse

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
    """Endpoint de métricas Prometheus."""
    return HttpResponse(generate_latest(), content_type=CONTENT_TYPE_LATEST)
