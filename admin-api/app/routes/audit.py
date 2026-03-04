# ================================================================
# 安全情报分析智能体 — 审计日志 API 路由
# 版本：v1.0
# 作者：alex (unix_sec@163.com)
# 日期：2026-03-04
# ================================================================

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.models.database import engine, get_db
from app.models.schemas import PagedResponse
from sqlalchemy import text

router = APIRouter(prefix="/audit-logs", tags=["审计日志"])


@router.get("", response_model=PagedResponse)
def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    action: Optional[str] = None,
    target_table: Optional[str] = None,
    operator: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db),
):
    """查询审计日志列表。"""
    conditions = ["1=1"]
    params = {}

    if action:
        conditions.append("action = :action")
        params["action"] = action
    if target_table:
        conditions.append("target_table = :target_table")
        params["target_table"] = target_table
    if operator:
        conditions.append("operator LIKE :operator")
        params["operator"] = f"%{operator}%"
    if date_from:
        conditions.append("DATE(created_at) >= :date_from")
        params["date_from"] = date_from
    if date_to:
        conditions.append("DATE(created_at) <= :date_to")
        params["date_to"] = date_to

    where = " AND ".join(conditions)
    offset = (page - 1) * page_size

    with engine.connect() as conn:
        total = conn.execute(
            text(f"SELECT COUNT(*) FROM audit_logs WHERE {where}"), params
        ).scalar()
        rows = conn.execute(
            text(
                f"SELECT * FROM audit_logs WHERE {where} "
                f"ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
            ),
            {**params, "limit": page_size, "offset": offset},
        ).fetchall()

    return PagedResponse(
        total=total or 0,
        page=page,
        page_size=page_size,
        items=[dict(row._mapping) for row in rows],
    )
