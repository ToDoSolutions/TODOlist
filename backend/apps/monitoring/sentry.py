"""Integración con Sentry para error tracking."""
import logging

logger = logging.getLogger(__name__)


def init_sentry():
    """Inicializa Sentry si está configurado."""
    from django.conf import settings
    sentry_dsn = getattr(settings, "SENTRY_DSN", "")
    if not sentry_dsn:
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.celery import CeleryIntegration
        from sentry_sdk.integrations.django import DjangoIntegration

        sentry_sdk.init(
            dsn=sentry_dsn,
            integrations=[DjangoIntegration(), CeleryIntegration()],
            traces_sample_rate=0.1,
            send_default_pii=False,
        )
        logger.info("Sentry initialized successfully")
    except ImportError:
        logger.warning("sentry-sdk not installed, skipping Sentry init")
    except Exception:
        logger.exception("Error initializing Sentry")
