"""Unit tests for resilient_call (ARCHITECTURE_REVIEW §B-6)."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock

import pytest

from sia.common.resilience import (
    CircuitOpenError,
    _is_retryable,
    resilient,
    resilient_call,
)
from sia.gateway.llm.circuit_breaker import CircuitBreaker


@pytest.fixture
def fresh_breaker():
    """A breaker that opens after 2 failures — keeps tests fast."""
    return CircuitBreaker(
        name="test",
        failure_threshold=2,
        recovery_timeout=timedelta(seconds=60),
        half_open_max=1,
    )


class TestIsRetryable:
    def test_connection_error_retryable(self):
        assert _is_retryable(ConnectionError("reset"))

    def test_timeout_retryable(self):
        import asyncio
        assert _is_retryable(asyncio.TimeoutError())
        assert _is_retryable(TimeoutError())

    def test_os_error_retryable(self):
        assert _is_retryable(OSError("broken pipe"))

    def test_value_error_not_retryable(self):
        assert not _is_retryable(ValueError("bad input"))

    def test_key_error_not_retryable(self):
        assert not _is_retryable(KeyError("missing"))


@pytest.mark.asyncio
async def test_success_on_first_call(fresh_breaker):
    fn = AsyncMock(return_value="ok")
    result = await resilient_call(fresh_breaker, fn)
    assert result == "ok"
    assert fn.await_count == 1
    assert fresh_breaker.success_count == 1


@pytest.mark.asyncio
async def test_retries_on_transient_then_success(fresh_breaker):
    # Fails once with ConnectionError, then succeeds.
    fn = AsyncMock(side_effect=[ConnectionError("reset"), "ok"])
    result = await resilient_call(fresh_breaker, fn, backoff_base=0.001)
    assert result == "ok"
    assert fn.await_count == 2


@pytest.mark.asyncio
async def test_non_retryable_raises_without_retry(fresh_breaker):
    fn = AsyncMock(side_effect=ValueError("bad"))
    with pytest.raises(ValueError, match="bad"):
        await resilient_call(fresh_breaker, fn)
    assert fn.await_count == 1  # no retries
    # non-transient errors don't dirty the breaker
    assert fresh_breaker.failure_count == 0


@pytest.mark.asyncio
async def test_exhausts_retries_and_raises(fresh_breaker):
    fn = AsyncMock(side_effect=ConnectionError("always fails"))
    with pytest.raises(ConnectionError):
        await resilient_call(fresh_breaker, fn, max_retries=3, backoff_base=0.001)
    # 3 attempts, each recorded as a failure
    assert fn.await_count == 3


@pytest.mark.asyncio
async def test_breaker_opens_then_fast_fails(fresh_breaker):
    """After threshold failures the breaker opens and we get CircuitOpenError."""
    fn = AsyncMock(side_effect=ConnectionError("down"))
    # Drive 2 attempts that each register 2 failures … actually max_retries=3
    # per call makes this exhaust after 1 call because threshold=2.
    with pytest.raises(ConnectionError):
        await resilient_call(fresh_breaker, fn, max_retries=3, backoff_base=0.001)
    assert fresh_breaker.is_open

    # Subsequent call fast-fails
    fn2 = AsyncMock(return_value="unused")
    with pytest.raises(CircuitOpenError):
        await resilient_call(fresh_breaker, fn2)
    fn2.assert_not_called()


@pytest.mark.asyncio
async def test_decorator_form(fresh_breaker):
    calls = []

    @resilient(fresh_breaker, backoff_base=0.001)
    async def flaky(x):
        calls.append(x)
        if len(calls) < 2:
            raise ConnectionError("transient")
        return x * 2

    result = await flaky(5)
    assert result == 10
    assert len(calls) == 2
