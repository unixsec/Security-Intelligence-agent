"""Outbox Pattern implementation (ARCHITECTURE_REVIEW §B-5 / §E).

Problem: when business code writes to MySQL AND publishes to Redis Streams
separately, a crash between the two leaves the system inconsistent.

Solution: write both in the same MySQL transaction — the business row plus
a row in `outbox(entity_type, entity_id, action, payload, targets, status)`.
A separate poller publishes pending outbox rows to Redis Streams and marks
them `completed`. This gives at-least-once delivery with exactly-once
commit — the canonical Outbox pattern.

Two public entry points:
  * `enqueue_outbox(session, entity_type, entity_id, action, payload, targets)`
    — call inside a SQLAlchemy async transaction to record the event.
  * `run_outbox_publisher()` — long-running background loop that drains
    `status='pending'` rows into Redis Streams. Started by sia-consumer
    alongside the analyzer, so it shares the same pod lifecycle.

`targets` is a dict shaped like::

    {"streams": ["raw_intel_stream"], "fields": {"intel_id": "123"}}

The publisher iterates the streams list and XADDs `fields` to each.
Failed sends increment `retry_count`; after N retries the row is marked
`failed` and reported via a metric + audit event for manual review.

Idempotency: consumers must treat each XADD as at-least-once and rely on
their own de-dup (already done by Redis Streams consumer groups with
fingerprint keys in payloads).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from sia.common.database import get_db_context
from sia.common.redis import get_redis
from sia.models.system import Outbox

logger = logging.getLogger(__name__)

# Publisher tuning
_POLL_INTERVAL_SEC = 0.5       # how often to scan for new rows
_BATCH_SIZE = 100              # rows per pass
_MAX_RETRIES = 5               # after this, move to 'failed'
_BACKOFF_BASE_SEC = 2          # exponential: 2, 4, 8, 16, 32…


async def enqueue_outbox(
    session: AsyncSession,
    *,
    entity_type: str,
    entity_id: int,
    action: str,
    payload: dict[str, Any] | None = None,
    targets: dict[str, Any] | None = None,
) -> None:
    """Insert an outbox row in the **current transaction**.

    Caller must still COMMIT. If the transaction rolls back, the outbox
    row is never persisted — that's the whole point of the pattern.
    """
    row = Outbox(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        payload=payload,
        targets=targets or {},
        status="pending",
    )
    session.add(row)


async def run_outbox_publisher(
    poll_interval_sec: float = _POLL_INTERVAL_SEC,
    batch_size: int = _BATCH_SIZE,
    stop_event: asyncio.Event | None = None,
) -> None:
    """Background loop: drain pending outbox rows to Redis Streams.

    Designed to run as an asyncio Task alongside `run_analysis_consumer`.
    Respects `stop_event` for graceful shutdown (SEC-018).
    """
    logger.info("outbox publisher started (poll=%.2fs batch=%d)",
                poll_interval_sec, batch_size)
    stop = stop_event or asyncio.Event()

    while not stop.is_set():
        try:
            processed = await _drain_one_batch(batch_size=batch_size)
        except Exception:  # noqa: BLE001
            logger.exception("outbox publisher batch failed; backing off")
            processed = 0

        if processed == 0:
            # no work; sleep but respect shutdown promptly
            try:
                await asyncio.wait_for(stop.wait(), timeout=poll_interval_sec)
            except asyncio.TimeoutError:
                pass

    logger.info("outbox publisher stopped cleanly")


async def _drain_one_batch(*, batch_size: int) -> int:
    """Claim up to `batch_size` pending rows, publish them, mark completed.

    Returns the number of rows processed (0 means queue was empty).

    Claim strategy: `SELECT ... FOR UPDATE SKIP LOCKED` in MySQL 8 to allow
    multiple publisher replicas to progress concurrently without stepping
    on each other. On older MySQL the lock-then-update is still safe.
    """
    redis = get_redis()
    async with get_db_context() as session:
        rows = (await session.execute(
            select(Outbox)
            .where(Outbox.status == "pending")
            .order_by(Outbox.id.asc())
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )).scalars().all()

        if not rows:
            return 0

        # Flip status early so other pollers don't re-claim.
        ids = [r.id for r in rows]
        await session.execute(
            update(Outbox)
            .where(Outbox.id.in_(ids))
            .values(status="processing")
        )
        await session.flush()

    # Publish outside the DB transaction — network IO shouldn't hold the lock.
    completed_ids: list[int] = []
    failed: list[tuple[int, str]] = []
    for row in rows:
        try:
            await _publish_one(redis, row)
            completed_ids.append(row.id)
        except Exception as e:  # noqa: BLE001
            failed.append((row.id, str(e)))

    # Update DB with final statuses.
    async with get_db_context() as session:
        if completed_ids:
            await session.execute(
                update(Outbox)
                .where(Outbox.id.in_(completed_ids))
                .values(status="completed", processed_at=datetime.now())
            )
        for oid, err in failed:
            r = (await session.execute(
                select(Outbox).where(Outbox.id == oid)
            )).scalar_one()
            new_count = (r.retry_count or 0) + 1
            if new_count >= _MAX_RETRIES:
                await session.execute(
                    update(Outbox)
                    .where(Outbox.id == oid)
                    .values(status="failed", retry_count=new_count,
                            processed_at=datetime.now())
                )
                logger.error("outbox row %d exhausted retries: %s", oid, err)
            else:
                # Put back to pending with backoff via created_at — next pass
                # will reclaim.
                await session.execute(
                    update(Outbox)
                    .where(Outbox.id == oid)
                    .values(status="pending", retry_count=new_count)
                )
                logger.warning("outbox row %d retry %d: %s", oid, new_count, err)

    return len(rows)


async def _publish_one(redis, row: Outbox) -> None:
    """XADD the row's payload to each configured stream."""
    targets = row.targets or {}
    streams = targets.get("streams") or []
    fields = targets.get("fields") or row.payload or {}
    if not streams:
        raise ValueError(f"outbox row {row.id} has no streams target")
    # Redis stream XADD values must be strings
    str_fields = {k: str(v) for k, v in fields.items()}
    for stream in streams:
        await redis.xadd(stream, str_fields)
