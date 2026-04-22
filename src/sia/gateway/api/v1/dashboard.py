"""Dashboard and system API endpoints."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends

from sia.gateway.api.auth import verify_api_key
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sia.common.database import get_db
from sia.gateway.api.schemas import DashboardStats, HealthResponse, ProviderStatus
from sia.models.intelligence import Intelligence, SecurityEvent
from sia.models.source import IntelSource

router = APIRouter(tags=["dashboard"], dependencies=[Depends(verify_api_key)])

_start_time = time.monotonic()


@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)):
    """System health check endpoint."""
    from sia import __version__

    # Check DB
    db_status = "healthy"
    try:
        await db.execute(select(func.count(Intelligence.id)))
    except Exception:
        db_status = "unhealthy"

    # Check Redis
    redis_status = "healthy"
    try:
        from sia.common.redis import get_redis
        r = get_redis()
        await r.ping()
    except Exception:
        redis_status = "unhealthy"

    return HealthResponse(
        status="healthy" if db_status == "healthy" and redis_status == "healthy" else "degraded",
        version=__version__,
        uptime_seconds=round(time.monotonic() - _start_time, 1),
        database=db_status,
        redis=redis_status,
    )


@router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """Get dashboard statistics."""
    from datetime import datetime, timedelta

    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # Total intelligence
    total = (await db.execute(
        select(func.count(Intelligence.id))
    )).scalar() or 0

    # Today collected
    today_collected = (await db.execute(
        select(func.count(Intelligence.id)).where(
            Intelligence.collected_at >= today_start
        )
    )).scalar() or 0

    # Active P0/P1
    p0_active = (await db.execute(
        select(func.count(Intelligence.id)).where(
            Intelligence.priority_level == "P0",
            Intelligence.processing_status.in_(["raw", "preprocessed", "analyzed"]),
        )
    )).scalar() or 0

    p1_active = (await db.execute(
        select(func.count(Intelligence.id)).where(
            Intelligence.priority_level == "P1",
            Intelligence.processing_status.in_(["raw", "preprocessed", "analyzed"]),
        )
    )).scalar() or 0

    # Active events
    active_events = (await db.execute(
        select(func.count(SecurityEvent.id)).where(
            SecurityEvent.status == "developing"
        )
    )).scalar() or 0

    # Active sources
    active_sources = (await db.execute(
        select(func.count(IntelSource.id)).where(
            IntelSource.status == "active"
        )
    )).scalar() or 0

    # Analysis queue size (approximate from Redis)
    queue_size = 0
    try:
        from sia.common.redis import STREAM_RAW_INTEL, get_redis
        r = get_redis()
        info = await r.xinfo_stream(STREAM_RAW_INTEL)
        queue_size = info.get("length", 0)
    except Exception:
        pass

    return DashboardStats(
        total_intel=total,
        today_collected=today_collected,
        p0_active=p0_active,
        p1_active=p1_active,
        active_events=active_events,
        active_sources=active_sources,
        analysis_queue_size=queue_size,
    )


@router.get("/dashboard/category-distribution")
async def get_category_distribution(db: AsyncSession = Depends(get_db)):
    """Get intelligence distribution by category."""
    result = await db.execute(
        select(Intelligence.primary_category, func.count(Intelligence.id).label("count"))
        .where(Intelligence.primary_category.isnot(None))
        .group_by(Intelligence.primary_category)
        .order_by(func.count(Intelligence.id).desc())
    )
    return [{"category": row[0], "count": row[1]} for row in result]


@router.get("/dashboard/priority-trend")
async def get_priority_trend(days: int = 7, db: AsyncSession = Depends(get_db)):
    """Get priority distribution trend over recent days."""
    from datetime import datetime, timedelta
    from sqlalchemy import cast, Date

    start = datetime.now() - timedelta(days=days)
    result = await db.execute(
        select(
            cast(Intelligence.collected_at, Date).label("date"),
            Intelligence.priority_level,
            func.count(Intelligence.id).label("count"),
        )
        .where(Intelligence.collected_at >= start)
        .group_by("date", Intelligence.priority_level)
        .order_by("date")
    )
    return [
        {"date": str(row[0]), "priority": row[1], "count": row[2]}
        for row in result
    ]


@router.get("/system/llm-providers")
async def get_llm_provider_status():
    """Get LLM provider status (requires gateway instance)."""
    # This will be populated when the app has a gateway instance
    return {"message": "LLM provider status available when gateway is initialized"}


@router.post("/system/reload-prompts")
async def reload_prompts():
    """Trigger prompt template hot-reload."""
    from sia.scheduler.jobs import job_reload_prompts
    await job_reload_prompts()
    return {"status": "reloaded"}
