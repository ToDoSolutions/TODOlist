"""
Root conftest.py loaded by pytest.

Bootstraps Django and the test database idempotently when pytest-django is
not loaded. This is required for mutmut 3.x because mutmut invokes
pytest.main() multiple times per process and also forks for each mutant.
Pytest-django is not fork-safe, so mutmut runs with `-p no:django` and this
conftest provides the minimal Django bootstrap.
"""
from __future__ import annotations

import os
import sys

# Mutmut 3.x inyecta trampolines que aumentan la profundidad del stack.
# Las automatizaciones con señales recursivas (CREATE_TASK -> TASK_CREATED)
# pueden rozar el límite por defecto (1000).
sys.setrecursionlimit(10000)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings_test")

import django

# mutmut 3.x forkea el proceso por cada mutante (os.fork). El backend
# OpenSSL de `cryptography` puede quedar en un estado inconsistente en el
# hijo (Fernet/AES-CBC lanza UnsupportedAlgorithm). Forzamos la
# re-inicialización del binding en el hijo para evitarlo.
if hasattr(os, "register_at_fork"):
    def _reset_crypto_backend_in_child():
        try:
            from cryptography.hazmat.bindings.openssl.binding import Binding
            Binding._binding = None
            Binding.init_static_locks()
        except Exception as exc:  # noqa: BLE001 - internals de cryptography
            import logging
            logging.getLogger(__name__).debug("crypto reset en fork falló: %s", exc)

    os.register_at_fork(after_in_child=_reset_crypto_backend_in_child)

django.setup()


def pytest_configure(config):
    """Setup Django test environment only if pytest-django is not active."""
    config.addinivalue_line(
        "markers",
        "django_db: mark the test as using the Django test database",
    )
    if config.pluginmanager.has_plugin("django"):
        return

    from django.test.runner import DiscoverRunner
    from django.test.utils import _TestState, setup_test_environment

    if not hasattr(_TestState, "saved_data"):
        setup_test_environment()
        _runner = DiscoverRunner(verbosity=0, interactive=False, keepdb=True)
        _runner.setup_databases()
