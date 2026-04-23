"""Integration test: audit hash chain actually persists and survives verify."""

from __future__ import annotations

import pytest

from tests.integration.conftest import requires_docker

pytestmark = [pytest.mark.integration, requires_docker]


@pytest.mark.asyncio
async def test_audit_chain_persists_and_verifies(db_session, sia_env):
    """Emit 3 audit events and confirm the chain validates."""
    import asyncio

    from sia.common.audit import _persist_with_chain, verify_chain

    events = [
        {"event": "user.login", "result": "success", "actor_id": 1,
         "actor_name": "alice"},
        {"event": "intel.export", "result": "success", "actor_id": 1,
         "actor_name": "alice", "target": "intelligence", "target_id": 42},
        {"event": "user.logout", "result": "success", "actor_id": 1,
         "actor_name": "alice"},
    ]
    for e in events:
        await _persist_with_chain(e)
        # Small yield to serialize writes
        await asyncio.sleep(0.01)

    checked, broken = await verify_chain(batch_size=100)
    assert checked >= 3
    assert broken == []


@pytest.mark.asyncio
async def test_audit_chain_detects_tamper(db_session, sia_env):
    """Direct UPDATE on audit_log should cause verify_chain to report breakage."""
    from sqlalchemy import select, update

    from sia.common.audit import _persist_with_chain, verify_chain
    from sia.models.system import AuditLog

    await _persist_with_chain({"event": "x", "result": "success"})
    await _persist_with_chain({"event": "y", "result": "success"})
    await _persist_with_chain({"event": "z", "result": "success"})

    # Attacker mutates details of middle row
    row = (await db_session.execute(
        select(AuditLog).order_by(AuditLog.id.asc()).limit(3)
    )).scalars().all()[1]
    await db_session.execute(
        update(AuditLog).where(AuditLog.id == row.id)
        .values(details={"event": "z", "result": "denied"})  # forgery
    )
    await db_session.commit()

    checked, broken = await verify_chain(batch_size=100)
    assert checked >= 3
    assert row.id in broken
