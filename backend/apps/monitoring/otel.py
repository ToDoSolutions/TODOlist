"""Instrumentación OpenTelemetry (opcional).

Se activa definiendo ``OTEL_ENABLED=1`` y el endpoint OTLP
``OTEL_EXPORTER_OTLP_ENDPOINT`` (Jaeger/Tempo). Traza request HTTP →
DB → Celery → llamadas externas (requests) en una sola traza distribuida.

Si los paquetes no están instalados (requirements-optional.txt) o la
env var está desactivada, es un no-op silencioso.
"""
import logging
import os

logger = logging.getLogger(__name__)


def init_otel():
    if os.environ.get("OTEL_ENABLED", "") not in ("1", "true", "True"):
        return
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.instrumentation.celery import CeleryInstrumentor
        from opentelemetry.instrumentation.django import DjangoInstrumentor
        from opentelemetry.instrumentation.requests import RequestsInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create({"service.name": "todolist-backend"})
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        trace.set_tracer_provider(provider)

        DjangoInstrumentor().instrument()
        CeleryInstrumentor().instrument()
        RequestsInstrumentor().instrument()
        logger.info("OpenTelemetry habilitado (OTLP exporter)")
    except ImportError:
        logger.warning(
            "OTEL_ENABLED=1 pero faltan paquetes: pip install -r requirements-optional.txt"
        )
    except Exception:
        logger.exception("Error inicializando OpenTelemetry")
