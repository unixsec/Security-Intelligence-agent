"""Unit tests for Redis-backed distributed lock (ARCHITECTURE_REVIEW §E.2)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from sia.scheduler.distributed_lock import redis_lock, with_leader_lock


class _FakeRedis:
    """Minimal fake: models SET NX EX + eval(DEL-if-match)."""

    def __init__(self):
        self.store: dict[str, str] = {}

    async def set(self, key, value, *, nx=False, ex=None):
        if nx and key in self.store:
            return False
        self.store[key] = value
        return True

    async def eval(self, script, n_keys, *args):
        key = args[0]
        token = args[1]
        if self.store.get(key) == token:
            self.store.pop(key, None)
            return 1
        return 0


@pytest.mark.asyncio
async def test_lock_acquires_then_releases():
    fake = _FakeRedis()
    with patch("sia.scheduler.distributed_lock.get_redis", return_value=fake):
        async with redis_lock("k", ttl_sec=60) as got:
            assert got is True
            assert "lock:k" in fake.store
        # Released on context exit
        assert "lock:k" not in fake.store


@pytest.mark.asyncio
async def test_lock_skipped_when_contended():
    fake = _FakeRedis()
    with patch("sia.scheduler.distributed_lock.get_redis", return_value=fake):
        async with redis_lock("k", ttl_sec=60) as got1:
            assert got1 is True
            async with redis_lock("k", ttl_sec=60) as got2:
                assert got2 is False  # already held
    assert "lock:k" not in fake.store


@pytest.mark.asyncio
async def test_release_does_not_free_another_holders_lock():
    """If our lock TTL expired and another holder grabbed it, we must not free theirs."""
    fake = _FakeRedis()
    with patch("sia.scheduler.distributed_lock.get_redis", return_value=fake):
        async with redis_lock("k", ttl_sec=60) as got:
            assert got is True
            # Simulate other holder overwriting after we've acquired.
            fake.store["lock:k"] = "other-token"
        # Exit attempts release but token mismatch → lock left for other holder
        assert fake.store.get("lock:k") == "other-token"


@pytest.mark.asyncio
async def test_with_leader_lock_runs_when_acquired():
    fake = _FakeRedis()
    calls = []

    @with_leader_lock("job", ttl_sec=60)
    async def my_job():
        calls.append(1)
        return "done"

    with patch("sia.scheduler.distributed_lock.get_redis", return_value=fake):
        result = await my_job()
    assert result == "done"
    assert calls == [1]


@pytest.mark.asyncio
async def test_with_leader_lock_skipped_when_already_held():
    fake = _FakeRedis()
    # Pre-seed the lock so decorator sees it as held.
    await fake.set("lock:job:job", "someone-else", nx=True, ex=60)
    calls = []

    @with_leader_lock("job", ttl_sec=60)
    async def my_job():
        calls.append(1)

    with patch("sia.scheduler.distributed_lock.get_redis", return_value=fake):
        result = await my_job()
    assert result is None
    assert calls == []


@pytest.mark.asyncio
async def test_release_swallows_redis_errors():
    """If Redis is unreachable during release, we must not crash the job."""
    fake = AsyncMock()
    fake.set = AsyncMock(return_value=True)
    fake.eval = AsyncMock(side_effect=Exception("redis down"))
    with patch("sia.scheduler.distributed_lock.get_redis", return_value=fake):
        async with redis_lock("k", ttl_sec=60) as got:
            assert got is True
        # no raise — release is best-effort
