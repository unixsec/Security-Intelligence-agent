"""Pytest fixtures for integration tests (ARCHITECTURE_REVIEW §B-13).

Uses testcontainers to spin up a MySQL 8 + Redis 7 per test session,
runs alembic migrations, and exposes an `AsyncClient` bound to a fresh
FastAPI app. These tests are skipped when Docker is unavailable
(e.g. Windows runners without Docker Desktop), so CI must run them on
Linux runners.

Markers:
    @pytest.mark.integration     — require MySQL + Redis
    @pytest.mark.slow            — > 5 s

Run::

    pytest -m integration tests/integration/ -v
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio


def _docker_available() -> bool:
    """Best-effort check that `docker ps` works. testcontainers fails less
    gracefully if the daemon is missing."""
    import shutil
    import subprocess
    if shutil.which("docker") is None:
        return False
    try:
        subprocess.run(["docker", "ps"], capture_output=True, check=True, timeout=5)
        return True
    except Exception:  # noqa: BLE001
        return False


_REASON = "Docker daemon unavailable — skipping integration tests."
requires_docker = pytest.mark.skipif(not _docker_available(), reason=_REASON)


def _services_already_provided() -> bool:
    """True when the runner has injected SIA_MYSQL_HOST + SIA_REDIS_HOST itself
    (e.g. GitHub Actions ``services:``). In that case we skip testcontainers
    and trust the provided values — much faster on CI.
    """
    return bool(os.environ.get("SIA_MYSQL_HOST")) and bool(os.environ.get("SIA_REDIS_HOST"))


@pytest.fixture(scope="session")
def mysql_container():
    if _services_already_provided():
        yield None  # already injected via env; nothing to start
        return
    if not _docker_available():
        pytest.skip(_REASON)
    from testcontainers.mysql import MySqlContainer
    with MySqlContainer("mysql:8.0",
                        username="sia_test",
                        password="sia_test_pw_CI_only",
                        dbname="sia_test") as mysql:
        yield mysql


@pytest.fixture(scope="session")
def redis_container():
    if _services_already_provided():
        yield None
        return
    if not _docker_available():
        pytest.skip(_REASON)
    from testcontainers.redis import RedisContainer
    with RedisContainer("redis:7-alpine") as redis:
        yield redis


@pytest.fixture(scope="session")
def sia_env(mysql_container, redis_container):
    """Populate SIA_* env vars to point the app at MySQL + Redis.

    Either uses values injected by the runner (GitHub Actions services) or
    binds to whatever testcontainers brought up.

    Must run before any `sia.config.get_settings()` call because @lru_cache
    captures the first result.
    """
    if mysql_container is not None:
        os.environ["SIA_MYSQL_HOST"] = mysql_container.get_container_host_ip()
        os.environ["SIA_MYSQL_PORT"] = str(mysql_container.get_exposed_port(3306))
        os.environ.setdefault("SIA_MYSQL_USER", "sia_test")
        os.environ.setdefault("SIA_MYSQL_PASSWORD", "sia_test_pw_CI_only")
        os.environ.setdefault("SIA_MYSQL_DATABASE", "sia_test")
    if redis_container is not None:
        os.environ["SIA_REDIS_HOST"] = redis_container.get_container_host_ip()
        os.environ["SIA_REDIS_PORT"] = str(redis_container.get_exposed_port(6379))
    os.environ["SIA_ENV"] = "test"
    os.environ.setdefault("SIA_AUTH_JWT_SECRET", "ci-test-jwt-secret-at-least-32-characters-long")
    os.environ.setdefault("SIA_AUTH_JWT_ALGORITHM", "HS256")
    os.environ.setdefault("SIA_API_KEY", "ci-test-api-key")
    os.environ.setdefault("SIA_MINIO_HOST", "localhost")
    os.environ.setdefault("SIA_MINIO_PORT", "9000")
    os.environ.setdefault("SIA_MINIO_ACCESS_KEY", "ci-minio-key")
    os.environ.setdefault("SIA_MINIO_SECRET_KEY", "ci-minio-secret-at-least-16-chars")
    # Force cache invalidation so tests get a fresh Settings
    from sia.config import get_settings
    get_settings.cache_clear()
    yield


@pytest_asyncio.fixture
async def db_session(sia_env) -> AsyncIterator:
    """A clean DB session per test; creates tables via metadata.create_all."""
    from sia.common.database import close_db, get_db_context, init_db
    await init_db()
    async with get_db_context() as s:
        yield s
    await close_db()


@pytest_asyncio.fixture
async def api_client(sia_env) -> AsyncIterator:
    """An httpx AsyncClient bound to the FastAPI app in-process.

    Uses ASGITransport so no real socket is opened — lightning fast.
    """
    from httpx import ASGITransport, AsyncClient

    from sia.common.database import close_db, init_db
    from sia.main import app

    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await close_db()
