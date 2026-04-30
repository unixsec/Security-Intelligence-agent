"""Rate limiter middleware for API endpoints.

FN-4: previous version held buckets in process memory, so a 4-replica API
deployment effectively gave each client 4× the configured rate. This
version evaluates each bucket atomically inside Redis (Lua script), so
all replicas share one limiter. Best-effort fallback to the in-process
bucket kicks in only when Redis is unavailable, so a Redis outage never
brings down the API.

Two rings:
  1. Default per-identity bucket — JWT subject digest, API-key digest, or
     client IP.
  2. Stricter login-route bucket keyed by IP (SEC-015) — credential
     stuffing protection.
"""

from __future__ import annotations

import hashlib
import logging
import time

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

logger = logging.getLogger(__name__)


# Lua atomic token-bucket evaluation:
#   KEYS[1] = bucket key
#   ARGV[1] = capacity (burst)
#   ARGV[2] = refill rate (tokens / sec)
#   ARGV[3] = now (ms since epoch)
# Returns: 1 if a token was consumed, 0 otherwise.
_LUA_BUCKET = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local data = redis.call('HMGET', key, 'tokens', 'last')
local tokens = tonumber(data[1])
local last = tonumber(data[2])
if tokens == nil then
  tokens = capacity
  last = now
end
local elapsed = (now - last) / 1000.0
if elapsed > 0 then
  tokens = math.min(capacity, tokens + elapsed * rate)
end
local allowed = 0
if tokens >= 1 then
  tokens = tokens - 1
  allowed = 1
end
redis.call('HMSET', key, 'tokens', tokens, 'last', now)
redis.call('PEXPIRE', key, 60000)
return allowed
"""


class _LocalBucket:
    """In-process token bucket, used when Redis is unreachable."""

    __slots__ = ("burst", "rate", "buckets")

    def __init__(self, *, requests_per_minute: int, burst: int | None = None):
        self.burst = burst or requests_per_minute
        self.rate = requests_per_minute / 60.0
        self.buckets: dict[str, tuple[float, float]] = {}

    def consume(self, key: str) -> bool:
        now = time.monotonic()
        tokens, last = self.buckets.get(key, (float(self.burst), now))
        tokens = min(self.burst, tokens + (now - last) * self.rate)
        if tokens >= 1.0:
            self.buckets[key] = (tokens - 1.0, now)
            return True
        self.buckets[key] = (tokens, now)
        return False


class RedisBucket:
    """Cluster-wide token bucket evaluated by the Lua script."""

    def __init__(self, *, name: str, capacity: int, rate_per_sec: float):
        self.name = name
        self.capacity = capacity
        self.rate = rate_per_sec
        self._sha: str | None = None
        # Local fallback used on Redis outage.
        self._local = _LocalBucket(
            requests_per_minute=int(rate_per_sec * 60),
            burst=capacity,
        )

    async def _ensure_loaded(self, redis) -> str:
        if self._sha is None:
            self._sha = await redis.script_load(_LUA_BUCKET)
        return self._sha

    async def consume(self, identity: str) -> bool:
        try:
            from sia.common.redis import get_redis
            redis = get_redis()
            sha = await self._ensure_loaded(redis)
            now_ms = int(time.time() * 1000)
            res = await redis.evalsha(
                sha, 1,
                f"sia:rl:{self.name}:{identity}",
                str(self.capacity), str(self.rate), str(now_ms),
            )
            return bool(int(res))
        except Exception:
            # Redis outage — degrade to per-replica bucket so we keep limiting,
            # just less precisely. Logging once a minute would be nice; for
            # now a debug log keeps the hot path quiet.
            logger.debug("Redis rate limiter unavailable; using local fallback", exc_info=True)
            return self._local.consume(identity)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-identity Redis-backed rate limiter (FN-4)."""

    # /metrics is mounted as an ASGI sub-app and must not be rate-limited
    # (Prometheus scrapes at high frequency).
    _HEALTH_PATHS = frozenset(
        {"/health", "/healthz", "/api/v1/health", "/api/health", "/metrics"}
    )

    def __init__(
        self,
        app,
        *,
        requests_per_minute: int = 60,
        login_requests_per_minute: int = 5,
        login_path_prefixes: tuple[str, ...] = (
            "/api/v1/auth/login",
            "/api/v1/auth/oidc",
            "/api/v1/auth/ldap",
        ),
        burst: int | None = None,
    ):
        super().__init__(app)
        self._default = RedisBucket(
            name="default",
            capacity=burst or requests_per_minute,
            rate_per_sec=requests_per_minute / 60.0,
        )
        self._login = RedisBucket(
            name="login",
            capacity=login_requests_per_minute,
            rate_per_sec=login_requests_per_minute / 60.0,
        )
        self._login_prefixes = login_path_prefixes

    # ─── Identity resolution (SEC-006) ─────────────────────────────────────
    def _identity(self, request: Request) -> str:
        # 1) Bearer JWT — decode-free digest (the auth path validates).
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            return "jwt:" + hashlib.sha256(auth[7:].encode()).hexdigest()[:16]
        # 2) API key header
        k = request.headers.get("x-api-key")
        if k:
            return "key:" + hashlib.sha256(k.encode()).hexdigest()[:16]
        # 3) Fall back to client IP (with proxy support)
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return "ip:" + fwd.split(",")[0].strip()
        return "ip:" + (request.client.host if request.client else "unknown")

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path.rstrip("/") or "/"
        # Health and Prometheus scrape paths bypass the limiter entirely.
        if path in self._HEALTH_PATHS or path.startswith("/metrics"):
            return await call_next(request)

        identity = self._identity(request)

        # Login endpoints: ALSO gated by the stricter bucket (in addition to
        # default). Both must admit. Keyed by IP to prevent a single source
        # from enumerating credentials across accounts.
        if any(path.startswith(p) for p in self._login_prefixes):
            ip = request.headers.get("x-forwarded-for", "")
            ip = ip.split(",")[0].strip() if ip else (
                request.client.host if request.client else "unknown"
            )
            if not await self._login.consume("loginip:" + ip):
                raise HTTPException(
                    status_code=429,
                    detail="Too many login attempts. Slow down.",
                )

        if not await self._default.consume(identity):
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Please slow down.",
            )
        return await call_next(request)
