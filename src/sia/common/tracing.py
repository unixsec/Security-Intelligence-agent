"""OpenTelemetry tracing wiring (OBS-2).

Activated only when ``settings.otlp_endpoint`` is non-empty. Auto-instruments:

  * FastAPI request handling (incoming spans)
  * SQLAlchemy queries (DB spans, with statement preview)
  * Redis commands (stream xadd / xreadgroup show up here)
  * httpx client (LLM provider calls + collector fetches)

We deliberately do **not** instrument the Anthropic / OpenAI SDKs separately;
they all sit on top of httpx, so the httpx instrumentor already captures the
remote call. Add a manual span inside ``LLMGateway._call_provider`` only if
you want the prompt name as an attribute (out of scope here).

Failure mode: any import or init error is caught and logged at WARN — tracing
is best-effort, never fatal.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_initialized = False


def init_tracing(*, service_name: str = "sia-api", service_version: str = "0.3.0") -> None:
    """Configure the global tracer provider + OTLP exporter, then auto-instrument.

    Idempotent: subsequent calls are no-ops. Reads ``SIA_OTLP_ENDPOINT`` (or
    falls back to settings) so test runs that hand-set the env see it.
    """
    global _initialized
    if _initialized:
        return

    endpoint = os.environ.get("SIA_OTLP_ENDPOINT", "")
    if not endpoint:
        try:
            from sia.config import get_settings
            endpoint = get_settings().otlp_endpoint or ""
        except Exception:  # pragma: no cover
            endpoint = ""
    if not endpoint:
        logger.info("OTLP endpoint not configured; tracing disabled")
        _initialized = True
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except Exception:
        logger.warning(
            "opentelemetry-sdk not importable — pip install opentelemetry-{sdk,exporter-otlp}"
        )
        _initialized = True
        return

    resource = Resource.create({
        "service.name": service_name,
        "service.version": service_version,
        "deployment.environment": os.environ.get("SIA_ENV", "dev"),
    })
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=endpoint, insecure=endpoint.startswith("http://"))
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    _instrument_libs()
    logger.info("OpenTelemetry tracing initialized (endpoint=%s)", endpoint)
    _initialized = True


def _instrument_libs() -> None:
    """Wire up auto-instrumentation libraries that are present.

    Each import is tolerant of the package being absent so a stripped-down
    container (e.g. the consumer-only image) doesn't crash on import.
    """
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor().instrument()
    except Exception:
        logger.debug("FastAPI instrumentation skipped", exc_info=True)

    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        SQLAlchemyInstrumentor().instrument()
    except Exception:
        logger.debug("SQLAlchemy instrumentation skipped", exc_info=True)

    try:
        from opentelemetry.instrumentation.redis import RedisInstrumentor
        RedisInstrumentor().instrument()
    except Exception:
        logger.debug("Redis instrumentation skipped", exc_info=True)

    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        HTTPXClientInstrumentor().instrument()
    except Exception:
        logger.debug("httpx instrumentation skipped", exc_info=True)


def shutdown_tracing() -> None:
    """Best-effort flush + shutdown the tracer provider."""
    try:
        from opentelemetry import trace
        provider = trace.get_tracer_provider()
        if hasattr(provider, "shutdown"):
            provider.shutdown()
    except Exception:
        logger.debug("tracer shutdown failed", exc_info=True)


__all__ = ["init_tracing", "shutdown_tracing"]
