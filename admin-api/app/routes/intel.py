# ================================================================
# 安全情报分析智能体 — 情报查询 API 路由
# 版本：v1.0
# 作者：alex (unix_sec@163.com)
# 日期：2026-03-04
# ================================================================

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.schemas import PagedResponse, RawIntelResponse, ScoredIntelResponse
from app.services.intel_service import IntelService

router = APIRouter(prefix="/intel", tags=["情报查询"])


@router.get("/raw", response_model=PagedResponse)
def list_raw_intel(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    source_name: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db),
):
    """查询原始情报列表。"""
    svc = IntelService(db)
    total, items = svc.list_raw_intel(
        page=page, page_size=page_size,
        status=status, source_name=source_name,
        date_from=date_from, date_to=date_to,
    )
    return PagedResponse(
        total=total, page=page, page_size=page_size,
        items=[RawIntelResponse.model_validate(i) for i in items],
    )


@router.get("/scored", response_model=PagedResponse)
def list_scored_intel(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    p_level: Optional[str] = None,
    intel_type: Optional[str] = None,
    severity: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    min_score: Optional[float] = None,
    db: Session = Depends(get_db),
):
    """查询已评分情报列表（按综合分降序）。"""
    svc = IntelService(db)
    total, items = svc.list_scored_intel(
        page=page, page_size=page_size,
        p_level=p_level, intel_type=intel_type, severity=severity,
        date_from=date_from, date_to=date_to, min_score=min_score,
    )
    return PagedResponse(
        total=total, page=page, page_size=page_size,
        items=[ScoredIntelResponse.model_validate(i) for i in items],
    )


@router.get("/scored/{intel_id}", response_model=ScoredIntelResponse)
def get_scored_intel(
    intel_id: int,
    db: Session = Depends(get_db),
):
    """查询单条已评分情报详情。"""
    svc = IntelService(db)
    intel = svc.get_scored_intel(intel_id)
    if not intel:
        raise HTTPException(status_code=404, detail="情报不存在")
    return ScoredIntelResponse.model_validate(intel)


@router.get("/events")
def list_event_tracks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """查询事件追踪主线列表。"""
    svc = IntelService(db)
    total, items = svc.list_event_tracks(page=page, page_size=page_size, status=status)
    return PagedResponse(total=total, page=page, page_size=page_size, items=items)
