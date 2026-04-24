"""Adapter-layer base classes and registry (SIA v0.3+).

Every extension point (collectors, push channels, LLM providers) derives
from `BaseAdapter`, and concrete classes register themselves with a
per-surface `Registry` instance.

The goal is to keep new integrations to **one file, zero core edits** —
add an intel source or push channel by dropping a module into
`sia.adapters.collector.*` or `sia.adapters.push.*` and using
`@registry.register("name")`.

Security / reliability invariants baked into BaseAdapter:
  * Every `run()` call is wrapped in a per-adapter metric+timer (subclasses
    implement `_do()` instead and get telemetry for free)
  * Secrets are loaded from `/etc/sia/secrets/` via config; adapters
    never `os.environ[...]` directly — config schema forces review
  * Failures raise `AdapterError` (or a subclass); callers fail-fast
    per dependency CircuitBreaker instead of generic exception soup.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
from typing import Any, Generic, TypeVar

logger = logging.getLogger(__name__)


# ─── Errors ──────────────────────────────────────────────────────────────

class AdapterError(Exception):
    """Base error raised by any adapter. Callers catch this to route to
    DLQ / retry / breaker accounting."""


class AdapterConfigError(AdapterError, ValueError):
    """Missing or malformed `AdapterConfig` — usually a 4xx on an admin UI."""


class AdapterTransportError(AdapterError, ConnectionError):
    """Transport-layer failure (network, TLS, auth). Retryable + CB-tracked."""


# ─── Config shape ────────────────────────────────────────────────────────

class AdapterConfig(dict):
    """Typed-ish dict carrying per-adapter config.

    We keep it a plain dict for JSON-over-DB friendliness, but expose
    typed getters so adapters can `self.cfg.require("url")` instead of
    `self.config["url"]` with no type narrowing.
    """

    def require(self, key: str, typ: type | None = None) -> Any:
        if key not in self or self[key] in ("", None):
            raise AdapterConfigError(f"adapter config missing required key: {key!r}")
        v = self[key]
        if typ is not None and not isinstance(v, typ):
            raise AdapterConfigError(
                f"adapter config key {key!r} has wrong type: expected {typ.__name__}, got {type(v).__name__}"
            )
        return v

    def opt(self, key: str, default: Any = None) -> Any:
        return self.get(key, default)


# ─── Base adapter ────────────────────────────────────────────────────────

class BaseAdapter(ABC):
    """Superclass for all adapters.

    Subclasses implement `_do(*args, **kwargs)`. `run()` wraps it with
    timing + logging + error translation, so every adapter picks up
    uniform telemetry for free.

    `kind` is the string key used by the registry (e.g. "rss", "feishu").
    `name` is an operator-facing identifier (e.g. "NVD", "Alice's email").
    """

    kind: str = ""

    def __init__(self, config: AdapterConfig | dict, *, name: str | None = None):
        self.cfg: AdapterConfig = (
            config if isinstance(config, AdapterConfig) else AdapterConfig(config)
        )
        self.name = name or self.cfg.opt("name") or self.kind

    # ─── Lifecycle hooks (default no-op; override as needed) ───────────

    async def aopen(self) -> None:
        """Acquire resources (HTTP clients, DB sessions). Idempotent."""
        return None

    async def aclose(self) -> None:
        """Release resources. Always called in a `finally`."""
        return None

    # ─── Entry point ───────────────────────────────────────────────────

    async def run(self, *args, **kwargs) -> Any:
        """Invoke the adapter with timing + standardized logging."""
        t0 = time.monotonic()
        try:
            result = await self._do(*args, **kwargs)
            dt_ms = int((time.monotonic() - t0) * 1000)
            logger.info("adapter %s/%s ok (%dms)", self.kind, self.name, dt_ms)
            return result
        except AdapterError:
            raise
        except Exception as e:  # noqa: BLE001 — translate to AdapterError
            dt_ms = int((time.monotonic() - t0) * 1000)
            logger.warning("adapter %s/%s FAILED (%dms): %s",
                           self.kind, self.name, dt_ms, e)
            raise AdapterError(f"{self.kind}/{self.name}: {e}") from e

    @abstractmethod
    async def _do(self, *args, **kwargs) -> Any:
        """Subclass implementation. Return type is adapter-specific."""
        ...


# ─── Registry ────────────────────────────────────────────────────────────

AdapterT = TypeVar("AdapterT", bound=BaseAdapter)


class Registry(Generic[AdapterT]):
    """Mapping from `kind` → adapter class.

    Usage::

        push_registry = Registry[PushAdapter]("push")

        @push_registry.register("feishu")
        class FeishuPusher(PushAdapter): ...

        # at runtime:
        pusher = push_registry.build("feishu", config={"webhook": "..."})
    """

    def __init__(self, surface: str):
        self.surface = surface
        self._classes: dict[str, type[AdapterT]] = {}

    def register(self, kind: str) -> Callable[[type[AdapterT]], type[AdapterT]]:
        def deco(cls: type[AdapterT]) -> type[AdapterT]:
            if kind in self._classes:
                raise RuntimeError(
                    f"{self.surface} adapter {kind!r} already registered "
                    f"by {self._classes[kind].__name__}"
                )
            cls.kind = kind  # type: ignore[attr-defined]
            self._classes[kind] = cls
            logger.debug("registered %s/%s → %s", self.surface, kind, cls.__name__)
            return cls
        return deco

    def get(self, kind: str) -> type[AdapterT]:
        try:
            return self._classes[kind]
        except KeyError:
            available = ", ".join(sorted(self._classes))
            raise AdapterConfigError(
                f"unknown {self.surface} adapter kind={kind!r}; "
                f"available: [{available}]"
            )

    def build(self, kind: str, config: AdapterConfig | dict, *,
              name: str | None = None) -> AdapterT:
        cls = self.get(kind)
        return cls(config, name=name)  # type: ignore[call-arg]

    def kinds(self) -> Iterator[str]:
        return iter(self._classes)
