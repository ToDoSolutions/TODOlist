"""Healthchecks por componente: DB, Redis, Celery.

``/health/`` → liveness básico (200 si el proceso responde).
``/health/ready/`` → readiness con checks por dependencia; 503 si alguna
falla. No requiere auth (lo usan load balancers / k8s probes).
"""
import logging

from django.db import connection
from django.http import JsonResponse

logger = logging.getLogger(__name__)


def _check_db():
    try:
        connection.ensure_connection()
        return True, "ok"
    except Exception as e:  # noqa: BLE001  # boundary intencional: fallo externo no rompe el flujo
        return False, str(e)[:200]


def _check_redis():
    try:
        from django.core.cache import cache
        cache.set("_health", "1", timeout=5)
        return (True, "ok") if cache.get("_health") == "1" else (False, "readback failed")
    except Exception as e:  # noqa: BLE001  # boundary intencional: fallo externo no rompe el flujo
        return False, str(e)[:200]


def _check_celery():
    """Ping a workers con timeout corto; no bloquea el healthcheck."""
    try:
        from config.celery import app as celery_app
        result = celery_app.control.ping(timeout=1.0)
        return (True, f"{len(result)} workers") if result else (False, "no workers")
    except Exception as e:  # noqa: BLE001  # boundary intencional: fallo externo no rompe el flujo
        return False, str(e)[:200]


def liveness(request):
    return JsonResponse({"status": "ok"})


def readiness(request):
    checks = {
        "db": _check_db(),
        "redis": _check_redis(),
        "celery": _check_celery(),
    }
    ok = all(c[0] for c in checks.values())
    return JsonResponse(
        {
            "status": "ok" if ok else "degraded",
            "checks": {k: {"ok": v[0], "detail": v[1]} for k, v in checks.items()},
        },
        status=200 if ok else 503,
    )
