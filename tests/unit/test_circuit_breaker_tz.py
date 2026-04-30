"""SEC-7: circuit-breaker timestamps must be tz-aware (UTC).

A naïve datetime mixed with a tz-aware ``datetime.now(timezone.utc)`` raises
``TypeError`` on subtraction, which would have masked recovery on hosts
running in a non-UTC timezone.
"""
from __future__ import annotations

from datetime import timedelta

from sia.gateway.llm.circuit_breaker import CircuitBreaker, CircuitState


def test_record_failure_sets_tzaware_timestamp():
    cb = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout=timedelta(seconds=1))
    cb.record_failure()
    assert cb.last_failure_time is not None
    assert cb.last_failure_time.tzinfo is not None
    assert cb.state == CircuitState.OPEN


def test_can_execute_arithmetic_does_not_throw():
    """Reproduces the original bug: tz-naïve - tz-aware would raise TypeError.

    ``can_execute`` must work whether or not the recovery period has elapsed.
    """
    cb = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout=timedelta(seconds=1))
    cb.record_failure()
    # Should not throw.
    assert cb.can_execute() in (True, False)
