"""Tests de borde para monitoring: healthchecks, middleware y security headers."""
import json
from unittest.mock import Mock, patch

import pytest
from django.test import Client

from apps.monitoring.health import (
    _check_celery,
    _check_db,
    _check_redis,
    readiness,
)
from apps.monitoring.middleware import MetricsMiddleware
from apps.monitoring.security_headers import SecurityHeadersMiddleware


class TestHealthChecks:
    def test_check_db_ok(self, db):
        ok, detail = _check_db()
        assert ok is True
        assert detail == "ok"

    def test_check_db_error(self):
        with patch(
            "apps.monitoring.health.connection.ensure_connection",
            side_effect=Exception("db caida"),
        ):
            ok, detail = _check_db()
        assert ok is False
        assert "db caida" in detail

    def test_check_redis_ok(self):
        with patch("django.core.cache.cache") as cache:
            cache.get.return_value = "1"
            ok, _ = _check_redis()
        assert ok is True

    def test_check_redis_readback_falla(self):
        with patch("django.core.cache.cache") as cache:
            cache.get.return_value = None
            ok, detail = _check_redis()
        assert ok is False
        assert "readback" in detail

    def test_check_redis_excepcion(self):
        with patch("django.core.cache.cache") as cache:
            cache.set.side_effect = Exception("redis down")
            ok, detail = _check_redis()
        assert ok is False
        assert "redis down" in detail

    def test_check_celery_con_workers(self):
        with patch("config.celery.app") as app:
            app.control.ping.return_value = [{"w1": {"ok": "pong"}}]
            ok, detail = _check_celery()
        assert ok is True
        assert "1 workers" in detail

    def test_check_celery_sin_workers(self):
        with patch("config.celery.app") as app:
            app.control.ping.return_value = []
            ok, detail = _check_celery()
        assert ok is False
        assert detail == "no workers"

    def test_check_celery_excepcion(self):
        with patch("config.celery.app") as app:
            app.control.ping.side_effect = Exception("broker caido")
            ok, detail = _check_celery()
        assert ok is False
        assert "broker" in detail

    def test_readiness_todo_ok(self, db):
        req = Mock()
        with patch("apps.monitoring.health._check_redis", return_value=(True, "ok")), \
             patch("apps.monitoring.health._check_celery", return_value=(True, "1 workers")):
            resp = readiness(req)
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data["status"] == "ok"
        assert set(data["checks"]) == {"db", "redis", "celery"}

    def test_readiness_degradado_503(self, db):
        req = Mock()
        with patch("apps.monitoring.health._check_redis", return_value=(False, "x")), \
             patch("apps.monitoring.health._check_celery", return_value=(True, "ok")):
            resp = readiness(req)
        assert resp.status_code == 503
        data = json.loads(resp.content)
        assert data["status"] == "degraded"
        assert data["checks"]["redis"]["ok"] is False


@pytest.mark.django_db
class TestHealthEndpoints:
    def test_liveness(self):
        resp = Client().get("/api/health/")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_readiness_endpoint(self):
        resp = Client().get("/api/health/ready/")
        assert resp.status_code in (200, 503)
        assert "checks" in resp.json()


class TestMetricsMiddleware:
    def _mw(self):
        resp = Mock(status_code=200)
        mw = MetricsMiddleware(lambda r: resp)
        return mw, resp

    def test_normaliza_id_numerico(self):
        mw, _ = self._mw()
        req = Mock(path="/api/tasks/123/", method="GET")
        mw(req)
        from apps.monitoring.metrics import REQUEST_COUNT
        # El label del counter usa {id}
        sample = [
            s for s in REQUEST_COUNT.collect()[0].samples
            if s.labels.get("endpoint") == "/api/tasks/{id}/"
        ]
        assert sample

    def test_normaliza_uuid_largo(self):
        mw, _ = self._mw()
        req = Mock(
            path="/api/sync/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/",
            method="GET",
        )
        mw(req)
        from apps.monitoring.metrics import REQUEST_COUNT
        sample = [
            s for s in REQUEST_COUNT.collect()[0].samples
            if s.labels.get("endpoint") == "/api/sync/{uuid}/"
        ]
        assert sample

    def test_no_normaliza_segmentos_cortos(self):
        mw, _ = self._mw()
        req = Mock(path="/api/tasks/mine/", method="GET")
        mw(req)
        from apps.monitoring.metrics import REQUEST_COUNT
        sample = [
            s for s in REQUEST_COUNT.collect()[0].samples
            if s.labels.get("endpoint") == "/api/tasks/mine/"
        ]
        assert sample

    def test_registra_status_y_metodo(self):
        resp = Mock(status_code=404)
        mw = MetricsMiddleware(lambda r: resp)
        req = Mock(path="/api/x/", method="DELETE")
        mw(req)
        from apps.monitoring.metrics import REQUEST_COUNT
        sample = [
            s for s in REQUEST_COUNT.collect()[0].samples
            if s.labels.get("endpoint") == "/api/x/"
            and s.labels.get("status") == "404"
            and s.labels.get("method") == "DELETE"
        ]
        assert sample


class TestSecurityHeaders:
    def _run(self, path, debug=True):
        from django.http import HttpResponse
        mw = SecurityHeadersMiddleware(lambda r: HttpResponse())
        req = Mock(path=path)
        with patch("apps.monitoring.security_headers.settings") as st:
            st.DEBUG = debug
            out = mw(req)
        return out

    def test_api_csp_estricta(self):
        resp = self._run("/api/tasks/")
        csp = resp["Content-Security-Policy"]
        assert "default-src 'none'" in csp
        assert "frame-ancestors 'none'" in csp

    def test_no_api_csp_permisiva(self):
        resp = self._run("/admin/")
        csp = resp["Content-Security-Policy"]
        assert "default-src 'self'" in csp
        assert "'unsafe-inline'" in csp

    def test_permissions_policy(self):
        resp = self._run("/api/")
        assert resp["Permissions-Policy"] == (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )

    def test_corp_siempre(self):
        resp = self._run("/api/")
        assert resp["Cross-Origin-Resource-Policy"] == "same-site"

    def test_coop_solo_prod(self):
        resp_dev = self._run("/api/", debug=True)
        resp_prod = self._run("/api/", debug=False)
        assert "Cross-Origin-Opener-Policy" not in resp_dev
        assert resp_prod["Cross-Origin-Opener-Policy"] == "same-origin"
