"""Resilience primitives for datastore calls (ARCHITECTURE_REVIEW §B-6).

LLM Gateway has its own CircuitBreaker (`sia.gateway.llm.circuit_breaker`).
This module adds an equivalent safety net for the **infrastructure layer**
— MySQL, Redis, Milvus, MinIO — so transient network glitches trigger
bounded retries, and persistent failures open the breaker and fast-fail
instead of cascading into connection-pool exhaustion.

Public API::

    from sia.common.resilience import (
        db_breaker, redis_breaker, milvus_breaker, minio_breaker,
        resilient_call,
    )

    # Wrap an async DB call:
    async def _load_intel(id: int):
        async with get_db_context() as s:
            ...

    intel = await resilient_call(db_breaker, _load_intel, 42)

Design:
  * Retry: exponential backoff up to 3 attempts (0.2s → 0.4s → 0.8s).
    Retry only on transport-level exceptions (DisconnectionError,
    OperationalError with transient codes, redis.ConnectionError).
  * Breaker: threshold 10 consecutive failures, 60s recovery window.
    Per-dependency, so a Redis outage doesn't open the MySQL breaker.
  * Fail-fast when breaker is OPEN — raises RuntimeError so the caller
    can serve a degraded response (5xx) without holding the worker.
"""

from __future__ import annotations

import asyncio
import functools
import logging
from datetime import timedelta
from typing import Awaitable, Callable, TypeVar

from sia.gateway.llm.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Separate breaker per dependency so faults are isolated.
db_breaker = CircuitBreaker(
    name="mysql",
    failure_threshold=10,
    recovery_timeout=timedelta(seconds=60),
    half_open_max=2,
)
redis_breaker = CircuitBreaker(
    name="redis",
    failure_threshold=10,
    recovery_timeout=timedelta(seconds=60),
    half_open_max=2,
)
milvus_breaker = CircuitBreaker(
    name="milvus",
    failure_threshold=5,
    recovery_timeout=timedelta(seconds=120),
    half_open_max=2,
)
minio_breaker = CircuitBreaker(
    name="minio",
    failure_threshold=5,
    recovery_timeout=timedelta(seconds=120),
    half_open_max=2,
)

_DEFAULT_MAX_RETRIES = 3
_DEFAULT_BACKOFF_BASE_SEC = 0.2
_DEFAULT_BACKOFF_CAP_SEC = 2.0


class CircuitOpenError(RuntimeError):
    """Raised when the breaker is open — caller should fail fast."""


def _is_retryable(exc: BaseException) -> bool:
    """True if exception is a transient transport problem worth retrying."""
    # Keep imports lazy so this module doesn't force-load sqlalchemy/redis at
    # startup (they're both already imported by consumers of resilient_call,
    # but lazy import keeps unit tests for this file independent).
    try:
        from sqlalchemy.exc import DisconnectionError, OperationalError
        if isinstance(exc, (DisconnectionError, OperationalError)):
            return True
    except ImportError:
        pass
    try:
        import redis.exceptions as re
        if isinstance(exc, (re.ConnectionError, re.TimeoutError, re.BusyLoadingError)):
            return True
    except ImportError:
        pass
    # Generic connection-reset family
    if isinstance(exc, (ConnectionError, TimeoutError, asyncio.TimeoutError, OSError)):
        return True
    return False


async def resilient_call(
    breaker: CircuitBreaker,
    fn: Callable[..., Awaitable[T]],
    *args,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    backoff_base: float = _DEFAULT_BACKOFF_BASE_SEC,
    backoff_cap: float = _DEFAULT_BACKOFF_CAP_SEC,
    **kwargs,
) -> T:
    """Execute `fn(*args, **kwargs)` with CB gate + exponential retry.

    - If breaker is OPEN, raise CircuitOpenError immediately.
    - If fn raises a retryable transport exception, retry with backoff.
    - If fn raises any other exception, do NOT retry; record failure
      only for transport-class exceptions so breaker stays stable.
    """
    if not breaker.can_execute():
        raise CircuitOpenError(f"circuit breaker '{breaker.name}' is OPEN")

    last_exc: BaseException | None = None
    for attempt in range(max_retries):
        try:
            result = await fn(*args, **kwargs)
            breaker.record_success()
            return result
        except Exception as e:  # noqa: BLE001 — classify below
            last_exc = e
            if not _is_retryable(e):
                # non-transient (e.g. IntegrityError, ValueError) — propagate
                # without dirtying the breaker.
                raise
            breaker.record_failure()
            if attempt == max_retries - 1 or not breaker.can_execute():
                break
            # jittered exponential backoff
            delay = min(backoff_base * (2 ** attempt), backoff_cap)
            logger.warning(
                "resilient_call [%s] attempt %d/%d failed: %s; retrying in %.2fs",
                breaker.name, attempt + 1, max_retries, e, delay,
            )
            await asyncio.sleep(delay)

    assert last_exc is not None
    raise last_exc


def resilient(breaker: CircuitBreaker, **retry_kwargs):
    """Decorator form of resilient_call.

    Usage::

        @resilient(db_breaker)
        async def load_user(uid: int) -> User: ...
    """
    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            return await resilient_call(breaker, fn, *args, **retry_kwargs, **kwargs)
        return wrapper
    return decorator
