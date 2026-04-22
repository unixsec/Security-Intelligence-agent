"""Redis connection and stream utilities."""

from __future__ import annotations

import os

import redis.asyncio as aioredis

from sia.config import get_settings

_redis_client: aioredis.Redis | None = None


# Stream names
STREAM_RAW_INTEL = "raw_intel_stream"
STREAM_ANALYZED = "analyzed_stream"
STREAM_EMERGENCY = "emergency_stream"
STREAM_PUSH_TASK = "push_task_stream"
STREAM_FEEDBACK = "feedback_stream"
STREAM_DLQ = "dead_letter_stream"


def _build_url_and_kwargs() -> tuple[str, dict]:
    """Construct redis URL + extra kwargs, honoring TLS settings (SEC-007)."""
    s = get_settings().redis
    auth = f":{s.password}@" if s.password else ""
    scheme = "rediss" if s.tls_enabled else "redis"
    url = f"{scheme}://{auth}{s.host}:{s.port}/{s.db}"
    kwargs: dict = {"decode_responses": True}
    if s.tls_enabled:
        kwargs["ssl_cert_reqs"] = "required"
        if s.tls_ca_path and os.path.exists(s.tls_ca_path):
            kwargs["ssl_ca_certs"] = s.tls_ca_path
    return url, kwargs


def get_redis() -> aioredis.Redis:
    """Get or create the Redis client singleton."""
    global _redis_client
    if _redis_client is None:
        url, kwargs = _build_url_and_kwargs()
        _redis_client = aioredis.from_url(url, **kwargs)
    return _redis_client


async def close_redis() -> None:
    """Close the Redis connection."""
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None


async def ensure_consumer_groups() -> None:
    """Create consumer groups for all streams (idempotent)."""
    r = get_redis()
    groups = [
        (STREAM_RAW_INTEL, "analyzer-group"),
        (STREAM_ANALYZED, "reporter-group"),
        (STREAM_EMERGENCY, "reporter-emergency"),
        (STREAM_PUSH_TASK, "pusher-group"),
        (STREAM_FEEDBACK, "analyzer-feedback"),
        (STREAM_DLQ, "ops-review"),
    ]
    for stream, group in groups:
        try:
            await r.xgroup_create(stream, group, id="0", mkstream=True)
        except aioredis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise


async def publish_to_stream(stream: str, data: dict) -> str:
    """Publish a message to a Redis stream. Returns the message ID."""
    r = get_redis()
    msg_id: str = await r.xadd(stream, data)
    return msg_id
