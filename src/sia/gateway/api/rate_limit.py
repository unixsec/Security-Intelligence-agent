"""Rate limiter middleware for API endpoints.

Two rings:
  1. Global middleware — per-client bucket using the first available identity:
     JWT subject, API key (SHA-256 digest), or client IP.
  2. Path-specific stricter limit (SEC-015) — login route: 5 req/min/IP.
     Applied in-middleware based on path matching.
"""

from __future__ import annotations

import hashlib
import logging
import time

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

logger = logging.getLogger(__name__)


class TokenBucket:
    """One bucket per identity."""

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


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-identity token-bucket limiter.

    Args:
        app: ASGI app.
        requests_per_minute: default bucket RPM for all paths.
        login_requests_per_minute: separate stricter bucket for auth endpoints
            (SEC-015). Defaults to 5/min.
        login_path_prefixes: paths counted as login attempts.
    """

    _HEALTH_PATHS = frozenset(
        {"/health", "/healthz", "/api/v1/health", "/api/health"}
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
        self._default = TokenBucket(requests_per_minute=requests_per_minute, burst=burst)
        self._login = TokenBucket(requests_per_minute=login_requests_per_minute, burst=login_requests_per_minute)
        self._login_prefixes = login_path_prefixes

    # ─── Identity resolution (SEC-006) ─────────────────────────────────────
    def _identity(self, request: Request) -> str:
        # 1) Bearer JWT — decode-free, use token's 10-char digest so we don't
        #    parse on every request. Attackers can rotate tokens, but that's
        #    protected by the login limiter + DB-backed refresh rotation.
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            return "jwt:" + hashlib.sha256(auth[7:].encode()).hexdigest()[:16]
        # 2) API key header
        k = request.headers.get("x-api-key")
        if k:
            return "key:" + hashlib.sha256(k.encode()).hexdigest()[:16]
        # 3) fall back to client IP (with proxy support)
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return "ip:" + fwd.split(",")[0].strip()
        return "ip:" + (request.client.host if request.client else "unknown")

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path.rstrip("/")
        if path in self._HEALTH_PATHS:
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
            if not self._login.consume("loginip:" + ip):
                raise HTTPException(
                    status_code=429,
                    detail="Too many login attempts. Slow down.",
                )

        if not self._default.consume(identity):
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Please slow down.",
            )
        return await call_next(request)
