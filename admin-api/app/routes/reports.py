# ================================================================
# 安全情报分析智能体 — 报告管理 API 路由
# 版本：v1.0
# 作者：alex (unix_sec@163.com)
# 日期：2026-03-04
# ================================================================

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.schemas import PagedResponse, ReportResponse, SuccessResponse

router = APIRouter(prefix="/reports", tags=["报告管理"])


@router.get("", response_model=PagedResponse)
def list_reports(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    report_type: Optional[str] = None,
    report_version: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """获取报告列表。"""
    from sqlalchemy import text
    from app.models.database import engine

    conditions = ["1=1"]
    params = {}
    if report_type:
        conditions.append("report_type = :report_type")
        params["report_type"] = report_type
    if report_version:
        conditions.append("report_version = :report_version")
        params["report_version"] = report_version
    if status:
        conditions.append("status = :status")
        params["status"] = status

    where = " AND ".join(conditions)
    offset = (page - 1) * page_size

    with engine.connect() as conn:
        total = conn.execute(
            text(f"SELECT COUNT(*) FROM reports WHERE {where}"), params
        ).scalar()
        rows = conn.execute(
            text(
                f"SELECT * FROM reports WHERE {where} "
                f"ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
            ),
            {**params, "limit": page_size, "offset": offset},
        ).fetchall()

    items = [dict(row._mapping) for row in rows]
    return PagedResponse(total=total or 0, page=page, page_size=page_size, items=items)


@router.get("/{report_id}")
def get_report(report_id: int, db: Session = Depends(get_db)):
    """获取报告详情（含完整内容）。"""
    from sqlalchemy import text
    from app.models.database import engine

    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM reports WHERE id = :id"), {"id": report_id}
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="报告不存在")
    return dict(row._mapping)


@router.post("/{report_id}/regenerate", response_model=SuccessResponse)
def regenerate_report(report_id: int, db: Session = Depends(get_db)):
    """触发报告重新生成。"""
    from sqlalchemy import text
    from app.models.database import engine
    import requests
    from app.config import get_settings

    settings = get_settings()

    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT report_type, period_start, period_end FROM reports WHERE id = :id"),
            {"id": report_id},
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="报告不存在")

    report_data = dict(row._mapping)
    try:
        resp = requests.post(
            f"{settings.dify_api_base}/workflows/run",
            headers={"Authorization": f"Bearer {settings.dify_api_key}"},
            json={
                "inputs": {
                    "report_type": report_data["report_type"],
                    "regenerate": True,
                    "report_id": report_id,
                },
                "user": "admin-api",
            },
            timeout=30,
        )
        resp.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"触发重新生成失败: {e}")

    return SuccessResponse(message="报告重新生成任务已提交")
