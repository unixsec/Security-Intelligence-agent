"""Source management API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from sia.common.database import get_db
from sia.gateway.api.auth import verify_api_key
from sia.gateway.api.schemas import SourceCreate, SourceResponse
from sia.models.source import IntelSource

router = APIRouter(prefix="/sources", tags=["sources"], dependencies=[Depends(verify_api_key)])


@router.get("", response_model=list[SourceResponse])
async def list_sources(db: AsyncSession = Depends(get_db)):
    """List all intelligence sources."""
    result = await db.execute(select(IntelSource).order_by(IntelSource.name))
    return [SourceResponse.model_validate(s) for s in result.scalars().all()]


@router.post("", response_model=SourceResponse, status_code=201)
async def create_source(
    body: SourceCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new intelligence source."""
    source = IntelSource(
        name=body.name,
        name_en=body.name_en,
        source_type=body.source_type,
        url=body.url,
        fetch_interval=body.fetch_interval,
        language=body.language,
        default_category=body.default_category,
        reliability=body.reliability,
        status="active",
    )
    db.add(source)
    await db.flush()
    return SourceResponse.model_validate(source)


@router.get("/{source_id}", response_model=SourceResponse)
async def get_source(source_id: int, db: AsyncSession = Depends(get_db)):
    """Get source by ID."""
    result = await db.execute(
        select(IntelSource).where(IntelSource.id == source_id)
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return SourceResponse.model_validate(source)


@router.put("/{source_id}/toggle")
async def toggle_source(source_id: int, db: AsyncSession = Depends(get_db)):
    """Toggle source active/paused status."""
    result = await db.execute(
        select(IntelSource).where(IntelSource.id == source_id)
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    new_status = "paused" if source.status == "active" else "active"
    await db.execute(
        update(IntelSource)
        .where(IntelSource.id == source_id)
        .values(status=new_status)
    )
    return {"id": source_id, "status": new_status}


@router.post("/{source_id}/collect")
async def trigger_collection(source_id: int, db: AsyncSession = Depends(get_db)):
    """Manually trigger collection for a source."""
    from sia.collector.service import collect_from_source

    result = await db.execute(
        select(IntelSource).where(IntelSource.id == source_id)
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    source_config = {
        "id": source.id,
        "name": source.name,
        "type": source.source_type,
        "url": source.url,
        "timeout_seconds": source.fetch_timeout or 30,
        "headers": source.custom_headers or {},
    }
    count = await collect_from_source(source_config)
    return {"source_id": source_id, "collected": count}
