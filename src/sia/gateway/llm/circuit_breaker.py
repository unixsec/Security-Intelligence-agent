"""Circuit breaker for LLM provider failover."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum

# SEC-7: keep all datetime arithmetic in UTC to match the rest of the codebase
# (jwt.py / audit.py / config). Mixing naïve and tz-aware datetimes silently
# produces wrong timeouts on hosts that use a non-UTC timezone.
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreaker:
    """Per-provider circuit breaker to detect persistent failures.

    Callers invoke can_execute() / record_success() / record_failure() from
    asyncio code. Under a single event loop these mutations are already
    serialized, so no explicit lock is required.
    """

    name: str
    failure_threshold: int = 5
    recovery_timeout: timedelta = field(default_factory=lambda: timedelta(seconds=300))
    half_open_max: int = 3

    state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    failure_count: int = field(default=0, init=False)
    success_count: int = field(default=0, init=False)
    last_failure_time: datetime | None = field(default=None, init=False)
    half_open_count: int = field(default=0, init=False)

    def can_execute(self) -> bool:
        """Check if the circuit allows execution."""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            if (
                self.last_failure_time
                and _utcnow() - self.last_failure_time > self.recovery_timeout
            ):
                self.state = CircuitState.HALF_OPEN
                self.half_open_count = 0
                self._publish_state()
                logger.info("Circuit breaker %s: OPEN -> HALF_OPEN", self.name)
                return True
            return False

        # HALF_OPEN
        return self.half_open_count < self.half_open_max

    def _publish_state(self) -> None:
        """OBS-1: surface state transitions to Prometheus."""
        try:
            from sia.common.metrics import circuit_state as _g
            _g.labels(name=self.name).set(
                {CircuitState.CLOSED: 0, CircuitState.HALF_OPEN: 1, CircuitState.OPEN: 2}[self.state]
            )
        except Exception:
            # metrics is best-effort; never break the breaker
            pass

    def record_success(self) -> None:
        self.success_count += 1
        if self.state == CircuitState.HALF_OPEN:
            self.half_open_count += 1
            if self.half_open_count >= self.half_open_max:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self._publish_state()
                logger.info("Circuit breaker %s: HALF_OPEN -> CLOSED", self.name)
        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = _utcnow()
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            self._publish_state()
            logger.warning("Circuit breaker %s: HALF_OPEN -> OPEN", self.name)
        elif self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            self._publish_state()
            logger.warning(
                "Circuit breaker %s: CLOSED -> OPEN (failures=%d)",
                self.name, self.failure_count,
            )

    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN
