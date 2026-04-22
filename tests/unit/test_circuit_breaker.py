"""Tests for LLM circuit breaker."""

from datetime import timedelta

from sia.gateway.llm.circuit_breaker import CircuitBreaker, CircuitState


class TestCircuitBreaker:
    def test_initial_state_closed(self):
        cb = CircuitBreaker(name="test")
        assert cb.state == CircuitState.CLOSED
        assert cb.can_execute()

    def test_opens_after_threshold(self):
        cb = CircuitBreaker(name="test", failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert not cb.can_execute()

    def test_stays_closed_below_threshold(self):
        cb = CircuitBreaker(name="test", failure_threshold=5)
        for _ in range(4):
            cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        assert cb.can_execute()

    def test_success_resets_count(self):
        cb = CircuitBreaker(name="test", failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb.failure_count == 0
        assert cb.state == CircuitState.CLOSED

    def test_half_open_after_timeout(self):
        cb = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout=timedelta(seconds=0))
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        # With 0 timeout, should transition to HALF_OPEN immediately
        assert cb.can_execute()
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_closes_after_enough_successes(self):
        cb = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout=timedelta(seconds=0), half_open_max=2)
        cb.record_failure()
        cb.can_execute()  # Transitions to HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.HALF_OPEN  # Not enough successes yet
        cb.record_success()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_half_open_opens_on_failure(self):
        cb = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout=timedelta(seconds=0))
        cb.record_failure()
        cb.can_execute()  # Transitions to HALF_OPEN
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
