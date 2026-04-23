"""Unit tests for Outbox Pattern (ARCHITECTURE_REVIEW §B-5 / §E).

Full integration (real MySQL + Redis) is covered in tests/integration/;
here we exercise the publisher's decision logic with mocks.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_publish_one_xadds_to_all_streams():
    from sia.common.outbox import _publish_one
    from sia.models.system import Outbox

    redis = AsyncMock()
    row = Outbox(
        id=1,
        entity_type="intelligence",
        entity_id=42,
        action="create",
        payload={"intel_id": 42},
        targets={"streams": ["raw_intel_stream", "analyzed_stream"],
                 "fields": {"intel_id": 42, "source": "rss"}},
        status="pending",
    )

    await _publish_one(redis, row)

    assert redis.xadd.await_count == 2
    redis.xadd.assert_any_await(
        "raw_intel_stream", {"intel_id": "42", "source": "rss"}
    )
    redis.xadd.assert_any_await(
        "analyzed_stream", {"intel_id": "42", "source": "rss"}
    )


@pytest.mark.asyncio
async def test_publish_one_falls_back_to_payload_when_no_fields():
    from sia.common.outbox import _publish_one
    from sia.models.system import Outbox

    redis = AsyncMock()
    row = Outbox(
        id=2, entity_type="x", entity_id=1, action="create",
        payload={"foo": "bar"},
        targets={"streams": ["s1"]},  # no explicit 'fields' → use payload
        status="pending",
    )
    await _publish_one(redis, row)
    redis.xadd.assert_awaited_once_with("s1", {"foo": "bar"})


@pytest.mark.asyncio
async def test_publish_one_rejects_missing_streams():
    from sia.common.outbox import _publish_one
    from sia.models.system import Outbox

    redis = AsyncMock()
    row = Outbox(
        id=3, entity_type="x", entity_id=1, action="create",
        payload={"k": "v"}, targets={},  # no streams
        status="pending",
    )
    with pytest.raises(ValueError, match="no streams"):
        await _publish_one(redis, row)
    redis.xadd.assert_not_called()


@pytest.mark.asyncio
async def test_publisher_stops_on_event():
    """The publisher's stop_event flips cleanly without deadlock."""
    import asyncio

    from sia.common.outbox import run_outbox_publisher

    stop = asyncio.Event()

    async def _stop_soon():
        await asyncio.sleep(0.05)
        stop.set()

    # Run publisher; it will see an empty queue each poll and eventually stop.
    # Guard with overall timeout so a bug doesn't hang the test suite.
    async def _go():
        await asyncio.gather(
            asyncio.wait_for(run_outbox_publisher(poll_interval_sec=0.01,
                                                  stop_event=stop),
                             timeout=2.0),
            _stop_soon(),
        )

    try:
        await _go()
    except asyncio.TimeoutError:
        pytest.fail("publisher did not honor stop_event")
