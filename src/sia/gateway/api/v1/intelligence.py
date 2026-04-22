"""Intelligence API endpoints."""

from __future__ import annotations

import math

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sia.common.database import get_db
from sia.gateway.api.auth import verify_api_key
from sia.gateway.api.schemas import (
    IntelligenceDetail,
    IntelligenceListItem,
    IntelligenceQuery,
    PaginatedResponse,
)
from sia.models.intelligence import Intelligence

router = APIRouter(prefix="/intelligence", tags=["intelligence"], dependencies=[Depends(verify_api_key)])


@router.get("", response_model=PaginatedResponse)
async def list_intelligence(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    priority: str | None = None,
    category: str | None = None,
    status: str | None = None,
    keyword: str | None = None,
    sort_by: str = "collected_at",
    sort_order: str = "desc",
    db: AsyncSession = Depends(get_db),
):
    """List intelligence with filtering and pagination."""
    query = select(Intelligence)

    if priority:
        query = query.where(Intelligence.priority_level == priority)
    if category:
        query = query.where(Intelligence.primary_category == category)
    if status:
        query = query.where(Intelligence.processing_status == status)
    if keyword:
        # Escape LIKE special characters to prevent injection
        safe_kw = keyword.replace("%", r"\%").replace("_", r"\_")
        query = query.where(
            Intelligence.title.ilike(f"%{safe_kw}%", escape="\\")
            | Intelligence.content.ilike(f"%{safe_kw}%", escape="\\")
        )

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Sort — whitelist allowed columns to prevent column enumeration
    ALLOWED_SORT = {"collected_at", "published_at", "total_score", "priority_level", "id"}
    if sort_by not in ALLOWED_SORT:
        sort_by = "collected_at"
    sort_col = getattr(Intelligence, sort_by)
    if sort_order not in ("asc", "desc"):
        sort_order = "desc"
    if sort_order == "desc":
        query = query.order_by(sort_col.desc())
    else:
        query = query.order_by(sort_col.asc())

    # Paginate
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = [IntelligenceListItem.model_validate(r) for r in result.scalars().all()]

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if page_size else 0,
    )


@router.get("/{intel_id}", response_model=IntelligenceDetail)
async def get_intelligence(
    intel_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get intelligence detail by ID."""
    result = await db.execute(
        select(Intelligence).where(Intelligence.id == intel_id)
    )
    intel = result.scalar_one_or_none()
    if not intel:
        raise HTTPException(status_code=404, detail="Intelligence not found")
    return IntelligenceDetail.model_validate(intel)


@router.post("/{intel_id}/reanalyze")
async def reanalyze_intelligence(
    intel_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Trigger re-analysis of an intelligence item."""
    from sia.common.redis import STREAM_RAW_INTEL, publish_to_stream

    result = await db.execute(
        select(Intelligence.id).where(Intelligence.id == intel_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Intelligence not found")

    await publish_to_stream(STREAM_RAW_INTEL, {
        "intel_id": str(intel_id),
        "source_name": "reanalysis",
        "priority_hint": "high",
    })
    return {"status": "queued", "intel_id": intel_id}
