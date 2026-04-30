"""Audit log read-only endpoints (admin / auditor).

The audit hash chain is append-only and write paths live elsewhere
(`common/audit.py`). This module only exposes filtered reads so the
front-end audit viewer can render activity history.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from sia.auth.rbac import require_role
from sia.common.database import get_db
from sia.models.system import AuditLog

router = APIRouter(
    prefix="/audit-logs",
    tags=["audit"],
    dependencies=[Depends(require_role("admin"))],
)


class AuditEntry(BaseModel):
    id: int
    occurred_at: datetime
    actor: str
    actor_ip: str | None
    event_type: str
    entity_type: str | None
    entity_id: str | None
    action: str
    details: dict | None
    prev_hash: str
    current_hash: str

    model_config = {"from_attributes": True}


@router.get("", response_model=list[AuditEntry])
async def list_audit(
    actor: str | None = Query(None, description="Substring match on actor"),
    event_type: str | None = Query(None),
    action: str | None = Query(None),
    since: datetime | None = Query(None, description="Lower bound on occurred_at"),
    until: datetime | None = Query(None, description="Upper bound on occurred_at"),
    limit: int = Query(200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    q = select(AuditLog).order_by(desc(AuditLog.occurred_at)).limit(limit)
    if actor:
        q = q.where(AuditLog.actor.ilike(f"%{actor}%"))
    if event_type:
        q = q.where(AuditLog.event_type == event_type)
    if action:
        q = q.where(AuditLog.action == action)
    if since:
        q = q.where(AuditLog.occurred_at >= since)
    if until:
        q = q.where(AuditLog.occurred_at <= until)
    rows = (await db.execute(q)).scalars().all()
    return [AuditEntry.model_validate(r) for r in rows]


@router.get("/stats")
async def audit_stats(
    hours: int = Query(24, ge=1, le=24 * 30),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import func
    since = datetime.now() - timedelta(hours=hours)
    rows = (await db.execute(
        select(AuditLog.event_type, func.count(AuditLog.id))
        .where(AuditLog.occurred_at >= since)
        .group_by(AuditLog.event_type)
        .order_by(desc(func.count(AuditLog.id)))
    )).all()
    return [{"event_type": r[0], "count": r[1]} for r in rows]
