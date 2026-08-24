"""Middleware para capturar métricas de requests."""
import time
from .metrics import REQUEST_COUNT, REQUEST_LATENCY, API_CALLS


class MetricsMiddleware:
    """Captura métricas de cada request HTTP."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.time()
        response = self.get_response(request)
        duration = time.time() - start

        endpoint = request.path
        method = request.method
        status = response.status_code

        REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status).inc()
        REQUEST_LATENCY.labels(endpoint=endpoint).observe(duration)
        API_CALLS.labels(endpoint=endpoint, method=method).inc()

        return response
