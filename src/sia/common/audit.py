"""Structured audit logger (SEC-013) with tamper-evident hash chain.

Two channels:
  1. `sia.audit` logger — one JSON line per event, for SIEM/Loki ingestion.
  2. `audit_log` table — same event persisted with a SHA-256 hash chain so
     any after-the-fact modification breaks the chain and is detectable by
     `scripts/ops/verify_audit_chain.py`.

Usage::

    from sia.common.audit import audit

    audit(
        "user.login",
        actor_id=user.id, actor_name=user.username,
        target="user",   target_id=user.id,
        result="success", request=request,
    )

Hash chain rule (ARCHITECTURE_REVIEW §E.3):
    current_hash = SHA256( prev_hash || canonical_json(payload) )

where canonical_json sorts keys to defeat re-serialisation drift.
Genesis record uses prev_hash = "0" * 64.

The write to DB is best-effort: if it fails we still emit the log line and
log an internal error, because the SIEM channel is a secondary record and
audit MUST never block the business path. In practice MySQL availability
is checked at startup so this path is quiet except during outages.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

# Dedicated logger so operators can route audit events to a separate sink.
_logger = logging.getLogger("sia.audit")
_logger.propagate = False  # don't duplicate to root
if not _logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(_h)
    _logger.setLevel(logging.INFO)

_internal = logging.getLogger(__name__)

_GENESIS_HASH = "0" * 64


def audit(
    event: str,
    *,
    actor_id: int | None = None,
    actor_name: str | None = None,
    target: str | None = None,
    target_id: int | str | None = None,
    result: str = "success",
    request: Any = None,
    persist: bool = True,
    **extra: Any,
) -> None:
    """Emit a single audit event (logger line + optional DB persistence)."""
    payload: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "event": event,
        "result": result,
    }
    if actor_id is not None:
        payload["actor_id"] = actor_id
    if actor_name is not None:
        payload["actor_name"] = actor_name
    if target is not None:
        payload["target"] = target
    if target_id is not None:
        payload["target_id"] = target_id

    if request is not None:
        try:
            payload["ip"] = _client_ip(request)
            payload["path"] = request.url.path
            payload["method"] = request.method
            ua = request.headers.get("user-agent")
            if ua:
                payload["ua"] = ua[:200]
        except Exception:  # noqa: BLE001
            pass

    if extra:
        # Protect: never accept raw passwords/tokens by convention.
        for k in list(extra.keys()):
            if any(s in k.lower() for s in ("password", "secret", "token", "api_key")):
                extra[k] = "***REDACTED***"
        payload.update(extra)

    # Channel 1: logger (fire-and-forget)
    _logger.info(json.dumps(payload, ensure_ascii=False, default=str))

    # Channel 2: DB with hash chain (best-effort async)
    if persist:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_persist_with_chain(payload))
        except RuntimeError:
            # No running loop (e.g. called from sync code during tests). Skip DB.
            pass


async def _persist_with_chain(payload: dict[str, Any]) -> None:
    """Insert one AuditLog row, computing the SHA-256 hash chain.

    Locks the previous head row with ``SELECT … ORDER BY id DESC LIMIT 1 FOR UPDATE``
    so concurrent writers serialise on the chain tip. For MySQL, the InnoDB
    gap lock + the AUTO_INCREMENT ordering guarantee a well-defined hash chain.
    """
    from sqlalchemy import desc, select

    from sia.common.database import get_db_context
    from sia.models.system import AuditLog

    try:
        async with get_db_context() as session:
            row = (
                await session.execute(
                    select(AuditLog.current_hash)
                    .order_by(desc(AuditLog.id))
                    .limit(1)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            prev_hash = row or _GENESIS_HASH

            canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                   default=str).encode("utf-8")
            current = sha256(prev_hash.encode("ascii") + canonical).hexdigest()

            session.add(AuditLog(
                prev_hash=prev_hash,
                current_hash=current,
                event_type=payload.get("event", "unknown")[:50],
                entity_type=payload.get("target"),
                entity_id=str(payload["target_id"]) if payload.get("target_id") is not None else None,
                action=payload.get("result", "success")[:20],
                actor=(payload.get("actor_name") or str(payload.get("actor_id") or "system"))[:100],
                actor_ip=payload.get("ip"),
                details=payload,
            ))
    except Exception:  # noqa: BLE001
        _internal.exception("audit DB persist failed (event=%s)", payload.get("event"))


def _client_ip(request: Any) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


# ─── Verification helper (used by scripts/ops/verify_audit_chain.py) ──────

async def verify_chain(batch_size: int = 1000) -> tuple[int, list[int]]:
    """Walk `audit_log` in id order; recompute and compare hashes.

    Returns (rows_checked, list_of_broken_ids). An empty list means the
    chain is intact. Intended to run as a cron (daily) and alert on any
    non-empty result.
    """
    from sqlalchemy import select

    from sia.common.database import get_db_context
    from sia.models.system import AuditLog

    broken: list[int] = []
    rows_checked = 0
    prev = _GENESIS_HASH

    async with get_db_context() as session:
        offset = 0
        while True:
            result = await session.execute(
                select(AuditLog)
                .order_by(AuditLog.id.asc())
                .offset(offset)
                .limit(batch_size)
            )
            rows = result.scalars().all()
            if not rows:
                break
            for row in rows:
                rows_checked += 1
                canonical = json.dumps(row.details or {}, sort_keys=True,
                                       ensure_ascii=False, default=str).encode("utf-8")
                expected = sha256(prev.encode("ascii") + canonical).hexdigest()
                if row.prev_hash != prev or row.current_hash != expected:
                    broken.append(row.id)
                prev = row.current_hash
            offset += batch_size
    return rows_checked, broken
