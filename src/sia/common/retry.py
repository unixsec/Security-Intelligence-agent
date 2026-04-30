"""Standardised exception classes + helpers for retry logic.

FN-5: previously the analyzer consumer used a single ``except Exception``
branch and slept 5s on any error. That treats network blips and poison
messages identically, which masks real failures and DLQs everything that
might just be a transient hiccup.

Three categories of error:

* :class:`TransientError` — the operation might succeed if retried (HTTP
  5xx, connection reset, Redis down momentarily, rate-limit). Don't ack
  the source message; let the consumer redeliver after a backoff.

* :class:`PermanentError` — the operation will never succeed for this
  input (HTTP 4xx with a deterministic body, schema validation failure,
  rule violation). Ack and DLQ.

* Anything else — treat as permanent (poison message). DLQ + ack so the
  consumer never enters an infinite redelivery loop on a single bad input.

Plus :func:`exponential_backoff` for loops that do their own retry.
"""

from __future__ import annotations

import asyncio
import logging
import random

logger = logging.getLogger(__name__)


class TransientError(Exception):
    """Recoverable failure: retry without DLQing."""


class PermanentError(Exception):
    """Deterministic failure: send the offending message to DLQ."""


async def exponential_backoff(
    attempt: int,
    *,
    base: float = 1.0,
    cap: float = 60.0,
    jitter: float = 0.2,
) -> None:
    """Sleep ``base * 2 ** attempt`` with proportional jitter, capped at ``cap``.

    Use inside ``while True`` consumer loops. Reset ``attempt`` to 0 after
    a clean iteration so the wait collapses on recovery.
    """
    if attempt < 0:
        attempt = 0
    delay = min(cap, base * (2 ** attempt))
    if jitter:
        delay = delay * (1 + random.uniform(-jitter, jitter))
    delay = max(0.0, delay)
    logger.debug("backoff attempt=%d delay=%.2fs", attempt, delay)
    await asyncio.sleep(delay)


__all__ = ["TransientError", "PermanentError", "exponential_backoff"]
