"""Redis-backed distributed lock for APScheduler jobs (ARCHITECTURE_REVIEW §B-2).

APScheduler is embedded in `sia-api`. When the Deployment is scaled to 2+
replicas (HPA), each replica runs its own scheduler and will independently
fire the same cron. Without a cluster-wide lock, collection / reports would
run N times per trigger.

This module provides:
  - `redis_lock(key, ttl)` — a contextmanager that uses `SET NX EX` + a
    token to mint a lock, and a Lua script to release only the token you
    own (prevents accidentally freeing a lock a later holder acquired).
  - `with_leader_lock(job_id, ttl)` — a decorator that wraps an async
    function so only the replica holding `lock:job:<id>` actually runs it.

The design is a single-Redis "redlock-lite". It tolerates the single-node
failure mode of a managed Redis (since scheduler jobs are idempotent-ish,
we accept the usual redlock caveats — see Martin Kleppmann's critique).
For stronger guarantees, swap to Kubernetes Lease API.
"""

from __future__ import annotations

import contextlib
import functools
import logging
import secrets
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import TypeVar

from sia.common.redis import get_redis

logger = logging.getLogger(__name__)

# Lua to release a lock only if the token matches. Atomic vs naive DEL which
# could free a lock now held by someone else after TTL expiry + reacquire.
_RELEASE_LUA = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
else
    return 0
end
"""

T = TypeVar("T")


@contextlib.asynccontextmanager
async def redis_lock(key: str, ttl_sec: int = 300) -> AsyncIterator[bool]:
    """Acquire a Redis lock for `key`, yielding True on success, False otherwise.

    ttl_sec should exceed the longest expected job runtime — if the holder
    dies without releasing, another replica will only pick it up after TTL.
    """
    r = get_redis()
    lock_key = f"lock:{key}"
    token = secrets.token_hex(16)
    acquired = await r.set(lock_key, token, nx=True, ex=ttl_sec)
    if acquired:
        logger.debug("acquired distributed lock %s ttl=%ds token=%s…",
                     lock_key, ttl_sec, token[:8])
    try:
        yield bool(acquired)
    finally:
        if acquired:
            try:
                await r.eval(_RELEASE_LUA, 1, lock_key, token)
                logger.debug("released distributed lock %s", lock_key)
            except Exception:  # noqa: BLE001  — releasing is best-effort
                logger.warning("failed to release lock %s (will expire via TTL)",
                               lock_key, exc_info=True)


def with_leader_lock(
    job_id: str, ttl_sec: int = 300,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T | None]]]:
    """Decorator: wrap an async scheduler job so only one replica runs it.

    Usage::

        @with_leader_lock("collect_all", ttl_sec=3600)
        async def job_collect_all() -> None:
            ...

    If the lock is held by another replica the wrapper returns None without
    side effects. The lock auto-expires after ttl_sec regardless of crash,
    ensuring forward progress.
    """
    def decorator(fn: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T | None]]:
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs) -> T | None:
            async with redis_lock(f"job:{job_id}", ttl_sec=ttl_sec) as got:
                if not got:
                    logger.info("skip job=%s (another replica is leader)", job_id)
                    return None
                return await fn(*args, **kwargs)
        return wrapper
    return decorator
