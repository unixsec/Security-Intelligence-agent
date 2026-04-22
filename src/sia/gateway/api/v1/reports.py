"""Report API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from sia.gateway.api.auth import verify_api_key
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sia.common.database import get_db
from sia.gateway.api.schemas import ReportGenerateRequest, ReportListItem
from sia.models.report import Report

router = APIRouter(prefix="/reports", tags=["reports"], dependencies=[Depends(verify_api_key)])


@router.get("", response_model=list[ReportListItem])
async def list_reports(
    report_type: str | None = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """List recent reports."""
    query = select(Report).order_by(Report.generated_at.desc()).limit(limit)
    if report_type:
        query = query.where(Report.report_type == report_type)
    result = await db.execute(query)
    return [ReportListItem.model_validate(r) for r in result.scalars().all()]


@router.get("/{report_id}")
async def get_report(report_id: int, db: AsyncSession = Depends(get_db)):
    """Get full report by ID."""
    result = await db.execute(
        select(Report).where(Report.id == report_id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return {
        "id": report.id,
        "title": report.title,
        "report_type": report.report_type,
        "content": report.content_json,
        "status": report.status,
        "generated_at": report.generated_at,
        "period_start": report.period_start,
        "period_end": report.period_end,
        "stats": {
            "intel_total": report.intel_total,
            "intel_selected": report.intel_selected,
            "p0_count": report.p0_count,
            "p1_count": report.p1_count,
        },
    }


@router.post("/generate")
async def generate_report(body: ReportGenerateRequest):
    """Trigger report generation."""
    from sia.reporter.service import gather_report_data, save_and_distribute
    from datetime import datetime

    report_data = await gather_report_data(
        report_type=body.report_type,
        period_start=body.period_start,
        period_end=body.period_end,
    )
    content = {
        "executive_summary": f"On-demand {body.report_type} report",
        "generated_at": datetime.now().isoformat(),
    }
    result = await save_and_distribute(
        report_type=body.report_type,
        content=content,
        report_data=report_data,
    )
    return result
