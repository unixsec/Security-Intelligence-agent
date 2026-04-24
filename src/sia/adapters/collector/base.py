"""Collector adapter contract + registry.

Every intelligence source plugs in by subclassing `CollectorAdapter`
and calling `@collector_registry.register("<kind>")`. The contract is
intentionally tiny: one async `_do() -> list[RawIntelItem]`.

Cross-cutting concerns are free:
  * SSRF validation delegated to `sia.collector.url_validator`
  * HTTP client helpers in this module (subclasses call `self._safe_get()`)
  * Rate limiting per source via `_rate_gate()` using Redis

Authorized source catalogue (`config/intel_sources.yaml` sample):

    sources:
      - kind: rss
        name: "BleepingComputer"
        url: https://www.bleepingcomputer.com/feed/
      - kind: taxii
        name: "CISA STIX 2.1"
        url: https://www.cisa.gov/taxii2/collections/.../objects/
      - kind: misp
        name: "Company MISP"
        url: https://misp.internal/
        api_key: ...
      ...
"""

from __future__ import annotations

import hashlib
import logging
from abc import abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx

from sia.adapters.base import AdapterConfig, AdapterError, BaseAdapter, Registry
from sia.collector.url_validator import validate_source_url

logger = logging.getLogger(__name__)

# Max response size enforced at the adapter layer (20 MiB).
_MAX_RESPONSE_BYTES = 20 * 1024 * 1024


# ─── Canonical intel item shape (shared across adapters) ─────────────────

@dataclass
class RawIntelItem:
    """Canonicalized intelligence item produced by any collector adapter.

    Down-stream pipeline treats this as the single normalized type; source-
    specific fields ride in `extra`.
    """
    title: str
    content: str
    url: str
    published_at: datetime
    source_id: int
    source_name: str
    author: str | None = None
    language: str = "en"
    extra: dict = field(default_factory=dict)

    @property
    def fingerprint(self) -> str:
        raw = f"{self.title.strip().lower()}|{self.url.strip().lower()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ─── Adapter base class ──────────────────────────────────────────────────

class CollectorAdapter(BaseAdapter):
    """Base class for all intel source collectors.

    Subclasses implement:
        async def _do(self) -> list[RawIntelItem]

    And typically call one of the provided helpers:
        self._safe_get(url, headers=..., allowed_ct=...)
        self._rate_gate()
    """

    # Accepted Content-Type prefixes by default. Subclasses override.
    accepted_content_types: tuple[str, ...] = (
        "application/json", "application/xml", "application/rss",
        "application/atom", "text/xml", "text/html", "text/plain",
    )

    # Minimum seconds between successive fetches against the same source
    # (best-effort — runtime enforcement via Redis in _rate_gate).
    min_interval_sec: int = 60

    def __init__(self, config: AdapterConfig | dict, *, name: str | None = None):
        super().__init__(config, name=name)
        # Common source metadata
        self.source_id: int = self.cfg.opt("id", 0)
        self.source_name: str = self.cfg.opt("name", self.kind)
        self.timeout = self.cfg.opt("timeout_seconds", 30)
        self.max_items = self.cfg.opt("max_items", 200)
        self.allowed_hosts: set[str] | None = (
            set(self.cfg["allowed_hosts"]) if self.cfg.opt("allowed_hosts") else None
        )

    # ─── HTTP helpers ──────────────────────────────────────────────────

    def _build_http_client(self) -> httpx.AsyncClient:
        proxy = self.cfg.opt("proxy") or self.cfg.opt("https_proxy")
        return httpx.AsyncClient(
            timeout=self.timeout,
            proxy=proxy,
            follow_redirects=False,  # SSRF: re-validate every hop
            limits=httpx.Limits(max_connections=5, max_keepalive_connections=2),
            headers={"User-Agent": self.cfg.opt("user_agent", "SIA-Collector/1.0")},
        )

    async def _safe_get(
        self,
        client: httpx.AsyncClient,
        url: str,
        *,
        headers: dict | None = None,
        allowed_ct: tuple[str, ...] | None = None,
        max_redirects: int = 3,
    ) -> httpx.Response:
        """GET with SSRF + redirect re-validation + size cap + CT whitelist."""
        current = url
        allowed = allowed_ct or self.accepted_content_types
        for _ in range(max_redirects + 1):
            validate_source_url(current, allowed_hosts=self.allowed_hosts)
            resp = await client.get(current, headers=headers or {})
            if resp.is_redirect:
                nxt = resp.headers.get("location")
                if not nxt:
                    break
                current = str(httpx.URL(current).join(nxt))
                continue
            resp.raise_for_status()
            cl = resp.headers.get("content-length")
            if cl and int(cl) > _MAX_RESPONSE_BYTES:
                raise AdapterError(f"{self.name}: response too large ({cl}B)")
            if len(resp.content) > _MAX_RESPONSE_BYTES:
                raise AdapterError(
                    f"{self.name}: response too large ({len(resp.content)}B)"
                )
            ct = resp.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            if not any(ct.startswith(p) for p in allowed):
                raise AdapterError(
                    f"{self.name}: unexpected Content-Type {ct!r}; "
                    f"expected one of {allowed}"
                )
            return resp
        raise AdapterError(f"{self.name}: redirect loop starting at {url!r}")

    async def _rate_gate(self) -> None:
        """Per-source best-effort rate limiter using Redis SET NX EX.

        Blocks new fetches while a prior one's cooldown is active. If Redis
        is unavailable, fall through (availability > throttling).
        """
        if self.min_interval_sec <= 0:
            return
        try:
            from sia.common.redis import get_redis
            r = get_redis()
            key = f"rate:collector:{self.source_id}:{self.kind}"
            got = await r.set(key, "1", nx=True, ex=self.min_interval_sec)
            if not got:
                raise AdapterError(
                    f"{self.name}: rate limited; cooldown {self.min_interval_sec}s active"
                )
        except AdapterError:
            raise
        except Exception:  # noqa: BLE001
            logger.warning("rate gate: redis unreachable; skipping gate for %s",
                           self.name, exc_info=True)

    # ─── Subclass API ──────────────────────────────────────────────────

    @abstractmethod
    async def _do(self) -> list[RawIntelItem]:
        """Fetch + normalize; return ready-to-ingest items."""


# ─── Module-level registry ───────────────────────────────────────────────

collector_registry: Registry[CollectorAdapter] = Registry("collector")
