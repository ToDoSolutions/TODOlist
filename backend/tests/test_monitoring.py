from unittest.mock import patch

from django.http import HttpResponse
from django.test import RequestFactory

from apps.monitoring.metrics import metrics_view
from apps.monitoring.middleware import MetricsMiddleware


class TestMetricsMiddleware:
    def test_middleware(self):
        factory = RequestFactory()
        request = factory.get("/api/tasks/")
        request.method = "GET"

        response = HttpResponse()
        response.status_code = 200

        middleware = MetricsMiddleware(lambda r: response)

        with patch("apps.monitoring.middleware.REQUEST_COUNT") as mock_count, \
             patch("apps.monitoring.middleware.REQUEST_LATENCY") as mock_latency, \
             patch("apps.monitoring.middleware.API_CALLS") as mock_calls:
            result = middleware(request)
            assert result.status_code == 200
            mock_count.labels.assert_called_once_with(method="GET", endpoint="/api/tasks/", status=200)
            mock_latency.labels.assert_called_once_with(endpoint="/api/tasks/")
            mock_calls.labels.assert_called_once_with(endpoint="/api/tasks/", method="GET")


class TestMetricsView:
    def test_metrics_view(self, settings):
        settings.METRICS_TOKEN = "tok"
        factory = RequestFactory()
        request = factory.get("/metrics/", HTTP_AUTHORIZATION="Bearer tok")
        response = metrics_view(request)
        assert response.status_code == 200
        assert "text/plain" in response["Content-Type"]

    def test_metrics_view_forbidden_sin_auth(self, settings):
        """Sin token ni usuario staff, metrics_view devuelve 403 (no crashea)."""
        settings.METRICS_TOKEN = "tok"
        factory = RequestFactory()
        request = factory.get("/metrics/")
        response = metrics_view(request)
        assert response.status_code == 403
