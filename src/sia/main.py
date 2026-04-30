"""SIA — Security Intelligence Agent main application."""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sia import __version__
from sia.common.logging_redact import install_redaction
from sia.config import get_settings

logger = logging.getLogger(__name__)


class _JsonFormatter(logging.Formatter):
    """Compact single-line JSON formatter for cluster log pipelines."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        payload = {
            "ts": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def _configure_logging(settings) -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)
    # Replace handlers so re-init is idempotent.
    for h in list(root.handlers):
        root.removeHandler(h)
    handler = logging.StreamHandler()
    if settings.log_json_format:
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
        )
    root.addHandler(handler)
    install_redaction()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown."""
    settings = get_settings()

    _configure_logging(settings)

    # OBS-2: tracing must initialize before the first request so the
    # FastAPI instrumentor can hook the route handler. The function is a
    # no-op when SIA_OTLP_ENDPOINT is unset.
    try:
        from sia.common.tracing import init_tracing
        init_tracing(service_name="sia-api", service_version=__version__)
    except Exception:
        logger.exception("tracing init failed; continuing without traces")

    logger.info("SIA v%s starting (env=%s)", __version__, settings.env)

    # Initialize database
    from sia.common.database import init_db, close_db
    if settings.env in ("dev", "test"):
        await init_db()
        logger.info("Database tables created (dev/test mode)")

    # Initialize Redis consumer groups
    from sia.common.redis import ensure_consumer_groups, close_redis
    try:
        await ensure_consumer_groups()
        logger.info("Redis consumer groups initialized")
    except Exception:
        if settings.env in ("production", "prod"):
            logger.critical("Redis unavailable in production — aborting startup")
            raise
        logger.warning("Redis not available — stream features disabled (dev/test mode)")

    # Start scheduler
    scheduler = None
    if settings.env != "test":
        from sia.scheduler.service import create_scheduler
        scheduler = create_scheduler()
        scheduler.start()
        logger.info("Scheduler started")

    logger.info("SIA startup complete")

    yield

    # Shutdown
    logger.info("SIA shutting down")
    if scheduler:
        scheduler.shutdown(wait=True)
    # Stop the prompt-watcher if anything inside the process holds a manager
    # (the API itself doesn't, but the consumer/scheduler tasks may have one).
    try:
        from sia.gateway.llm.prompt_manager import PromptManager  # noqa: F401
    except Exception:
        pass
    await close_redis()
    await close_db()
    try:
        from sia.common.tracing import shutdown_tracing
        shutdown_tracing()
    except Exception:
        pass
    logger.info("SIA shutdown complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Security Intelligence Agent",
        description="AI-powered security intelligence collection, analysis, and reporting platform",
        version=__version__,
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    # Rate limiting — per-identity bucket + stricter bucket for login routes (SEC-006/015)
    from sia.gateway.api.rate_limit import RateLimitMiddleware
    rpm = 60 if settings.env == "dev" else 30
    app.add_middleware(
        RateLimitMiddleware,
        requests_per_minute=rpm,
        login_requests_per_minute=5,
    )

    # CORS — dev permissive, prod empty-origin by default
    if settings.env == "dev":
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    else:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[],
            allow_credentials=False,
            allow_methods=["GET", "POST", "PUT", "DELETE"],
            allow_headers=["*"],
        )

    # Register API routers
    from sia.gateway.api.v1.auth import router as auth_router
    from sia.gateway.api.v1.users import router as users_router
    from sia.gateway.api.v1.intelligence import router as intel_router
    from sia.gateway.api.v1.sources import router as source_router
    from sia.gateway.api.v1.reports import router as report_router
    from sia.gateway.api.v1.dashboard import router as dashboard_router
    # v0.4 admin panel additions
    from sia.gateway.api.v1.api_keys import router as api_keys_router
    from sia.gateway.api.v1.audit import router as audit_router
    from sia.gateway.api.v1.system_admin import router as system_admin_router

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(users_router, prefix="/api/v1")
    app.include_router(intel_router, prefix="/api/v1")
    app.include_router(source_router, prefix="/api/v1")
    app.include_router(report_router, prefix="/api/v1")
    app.include_router(dashboard_router, prefix="/api/v1")
    app.include_router(api_keys_router, prefix="/api/v1")
    app.include_router(audit_router, prefix="/api/v1")
    app.include_router(system_admin_router, prefix="/api/v1")

    # OBS-1: Prometheus scrape endpoint. Mounted as a sub-app so it
    # bypasses dependency injection and request validation, and is excluded
    # from rate-limiting via RateLimitMiddleware._HEALTH_PATHS.
    from prometheus_client import make_asgi_app
    # Touch the metrics module so all metric objects are registered before
    # the first scrape arrives.
    import sia.common.metrics  # noqa: F401
    app.mount("/metrics", make_asgi_app())

    @app.get("/")
    async def root():
        return {
            "name": "Security Intelligence Agent",
            "version": __version__,
            "docs": "/api/docs",
        }

    return app


app = create_app()
