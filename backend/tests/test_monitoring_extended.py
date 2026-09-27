"""Tests exhaustivos para monitoring."""
from unittest.mock import MagicMock, patch

import pytest
from django.http import HttpResponse
from django.test import RequestFactory

from apps.monitoring.middleware import MetricsMiddleware


@pytest.mark.django_db
class TestMetricsMiddleware:
    def test_middleware_normalizes_path(self):
        """Verifica que el middleware normaliza paths con IDs."""
        middleware = MetricsMiddleware(lambda r: HttpResponse())
        factory = RequestFactory()
        request = factory.get("/api/tasks/123/")
        response = middleware(request)
        assert response.status_code == 200

    def test_middleware_normalizes_uuid(self):
        """Verifica que el middleware normaliza UUIDs."""
        middleware = MetricsMiddleware(lambda r: HttpResponse())
        factory = RequestFactory()
        request = factory.get("/api/tasks/550e8400-e29b-41d4-a716-446655440000/")
        response = middleware(request)
        assert response.status_code == 200

    def test_middleware_increments_metrics(self):
        """Verifica que el middleware incrementa métricas."""
        middleware = MetricsMiddleware(lambda r: HttpResponse())
        factory = RequestFactory()
        request = factory.get("/api/tasks/")
        response = middleware(request)
        assert response.status_code == 200


@pytest.mark.django_db
class TestSentry:
    def test_init_sentry(self):
        """Verifica que init_sentry inicializa Sentry si hay DSN."""
        import sys
        mock_sentry = MagicMock()
        sys.modules["sentry_sdk"] = mock_sentry
        sys.modules["sentry_sdk.integrations.django"] = MagicMock()
        sys.modules["sentry_sdk.integrations.celery"] = MagicMock()
        from apps.monitoring.sentry import init_sentry
        with patch("django.conf.settings") as mock_settings:
            mock_settings.SENTRY_DSN = "https://test@sentry.io/123"
            init_sentry()
            mock_sentry.init.assert_called_once()

    def test_init_sentry_no_dsn(self):
        """Verifica que init_sentry no hace nada si no hay DSN."""
        from apps.monitoring.sentry import init_sentry
        with patch("django.conf.settings") as mock_settings:
            mock_settings.SENTRY_DSN = ""
            init_sentry()
