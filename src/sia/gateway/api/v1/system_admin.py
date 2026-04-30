"""Operations endpoints for the System admin panel.

Provides:
- circuit breaker statuses (LLM gateway + infrastructure)
- Redis Stream lag / DLQ queue length
- recent scheduled job activity (best-effort, from APScheduler memory)
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends

from sia.auth.rbac import require_role

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/system",
    tags=["system-admin"],
    dependencies=[Depends(require_role("admin"))],
)


# ─── Circuit breakers ─────────────────────────────────────────────────────

@router.get("/circuit-breakers")
async def list_circuit_breakers() -> list[dict[str, Any]]:
    """Return a snapshot of every circuit breaker's current state.

    Best-effort: relies on the LLMGateway singleton being importable. If
    nothing is initialised yet we return an empty list rather than 500.
    """
    out: list[dict[str, Any]] = []
    try:
        # LLM CB lookup — if a global gateway was attached on app startup it
        # will expose ``_breakers`` (dict of name -> CircuitBreaker).
        from sia.gateway.llm.gateway import LLMGateway  # noqa: F401
        # Walk all live gateway instances via gc — pragmatic and avoids
        # threading a singleton through the FastAPI app object.
        import gc
        for obj in gc.get_objects():
            if obj.__class__.__name__ == "LLMGateway":
                breakers = getattr(obj, "_breakers", {}) or {}
                for name, cb in breakers.items():
                    out.append({
                        "kind": "llm",
                        "name": name,
                        "state": getattr(cb, "state", None).value if getattr(cb, "state", None) else "unknown",
                        "failure_count": getattr(cb, "failure_count", 0),
                        "success_count": getattr(cb, "success_count", 0),
                        "last_failure_time": getattr(cb, "last_failure_time", None).isoformat()
                            if getattr(cb, "last_failure_time", None) else None,
                    })
                break
    except Exception:
        logger.exception("failed to enumerate LLM circuit breakers")

    # Infrastructure breakers (resilience layer) expose name + state via the
    # metric `sia_circuit_state`; reading them out of the metric registry is
    # cheaper than holding refs.
    try:
        from sia.common import metrics as _m
        # ``circuit_state`` Gauge keeps per-label samples; iterate them.
        for sample in _m.circuit_state.collect()[0].samples:
            if sample.name.endswith("circuit_state") and sample.labels:
                out.append({
                    "kind": "infra",
                    "name": sample.labels.get("name", "?"),
                    "state": _state_from_gauge(int(sample.value)),
                })
    except Exception:
        logger.debug("metrics circuit_state read failed", exc_info=True)
    return out


def _state_from_gauge(v: int) -> str:
    return {0: "closed", 1: "half_open", 2: "open"}.get(v, "unknown")


# ─── Redis Streams: lag + DLQ ─────────────────────────────────────────────

@router.get("/streams")
async def list_streams() -> list[dict[str, Any]]:
    """Return per-stream length + pending count for every SIA stream."""
    from sia.common.redis import (
        STREAM_ANALYZED,
        STREAM_DLQ,
        STREAM_EMERGENCY,
        STREAM_FEEDBACK,
        STREAM_PUSH_TASK,
        STREAM_RAW_INTEL,
        get_redis,
    )
    streams = [
        STREAM_RAW_INTEL,
        STREAM_ANALYZED,
        STREAM_EMERGENCY,
        STREAM_PUSH_TASK,
        STREAM_FEEDBACK,
        STREAM_DLQ,
    ]
    r = get_redis()
    out: list[dict[str, Any]] = []
    for name in streams:
        try:
            length = await r.xlen(name)
        except Exception:
            length = -1
        groups: list[dict[str, Any]] = []
        try:
            for g in await r.xinfo_groups(name):
                groups.append({
                    "name": g.get("name"),
                    "consumers": g.get("consumers", 0),
                    "pending": g.get("pending", 0),
                    "last_delivered": g.get("last-delivered-id"),
                })
        except Exception:
            pass
        out.append({"stream": name, "length": length, "groups": groups})
    return out


@router.get("/dlq")
async def peek_dlq(limit: int = 50) -> dict[str, Any]:
    """Peek the dead-letter stream so ops can review poison messages."""
    from sia.common.redis import STREAM_DLQ, get_redis
    r = get_redis()
    items: list[dict[str, Any]] = []
    try:
        # XRANGE returns oldest first; tail-like behaviour with REVRANGE.
        rows = await r.xrevrange(STREAM_DLQ, count=limit)
        for msg_id, fields in rows:
            items.append({"id": msg_id, "data": fields})
    except Exception:
        logger.exception("dlq peek failed")
    return {"stream": STREAM_DLQ, "items": items, "count": len(items)}


# ─── Scheduler ─────────────────────────────────────────────────────────────

@router.get("/scheduler/jobs")
async def list_jobs() -> list[dict[str, Any]]:
    """List APScheduler jobs (next run + last status best-effort)."""
    out: list[dict[str, Any]] = []
    try:
        import gc
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        for obj in gc.get_objects():
            if isinstance(obj, AsyncIOScheduler):
                for job in obj.get_jobs():
                    out.append({
                        "id": job.id,
                        "name": job.name,
                        "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                        "trigger": str(job.trigger),
                    })
                break
    except Exception:
        logger.debug("scheduler enumeration failed", exc_info=True)
    return out
