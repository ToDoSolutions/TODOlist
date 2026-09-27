"""Middleware para capturar métricas de requests."""
import time

from .metrics import API_CALLS, REQUEST_COUNT, REQUEST_LATENCY


class MetricsMiddleware:
    """Captura métricas de cada request HTTP."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.time()
        response = self.get_response(request)
        duration = time.time() - start

        # Normalizar path para evitar alta cardinalidad en Prometheus
        # /api/tasks/123/ → /api/tasks/{id}/
        endpoint = request.path
        parts = endpoint.split("/")
        normalized = []
        for part in parts:
            if part.isdigit():
                normalized.append("{id}")
            elif part and len(part) > 20 and "-" in part:
                normalized.append("{uuid}")
            else:
                normalized.append(part)
        endpoint = "/".join(normalized)

        method = request.method
        status = response.status_code

        REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status).inc()
        REQUEST_LATENCY.labels(endpoint=endpoint).observe(duration)
        API_CALLS.labels(endpoint=endpoint, method=method).inc()

        return response
