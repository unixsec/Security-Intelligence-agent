"""Reporter service — generates reports and handles distribution."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import func, select

from sia.common.database import get_db_context
from sia.common.redis import STREAM_PUSH_TASK, publish_to_stream
from sia.models.intelligence import Intelligence, SecurityEvent
from sia.models.report import PushLog, Report, ReportIntelMap

logger = logging.getLogger(__name__)


async def gather_report_data(
    *,
    ctx: Any = None,
    report_type: str = "daily",
    period_start: str | None = None,
    period_end: str | None = None,
) -> dict:
    """Gather data for report generation."""
    now = datetime.now()
    if period_end:
        end_dt = datetime.fromisoformat(period_end)
    else:
        end_dt = now

    if period_start:
        start_dt = datetime.fromisoformat(period_start)
    else:
        from datetime import timedelta
        if report_type == "daily":
            start_dt = end_dt - timedelta(days=1)
        elif report_type == "weekly":
            start_dt = end_dt - timedelta(days=7)
        else:
            start_dt = end_dt - timedelta(days=30)

    async with get_db_context() as session:
        # Get intelligence in period
        base_query = select(Intelligence).where(
            Intelligence.analyzed_at >= start_dt,
            Intelligence.analyzed_at <= end_dt,
            Intelligence.processing_status == "analyzed",
        )

        # Top items by score
        top_query = base_query.order_by(Intelligence.total_score.desc()).limit(20)
        result = await session.execute(top_query)
        top_items_raw = result.scalars().all()

        top_items = [
            {
                "id": i.id,
                "title": i.title,
                "title_zh": i.title_zh,
                "priority": i.priority_level,
                "category": i.primary_category,
                "total_score": float(i.total_score) if i.total_score else 0,
                "summary": i.summary or i.title,
                "cve_id": i.cve_id,
            }
            for i in top_items_raw
        ]

        # Statistics
        count_result = await session.execute(
            select(func.count(Intelligence.id)).where(
                Intelligence.collected_at >= start_dt,
                Intelligence.collected_at <= end_dt,
            )
        )
        total_collected = count_result.scalar() or 0

        p0_result = await session.execute(
            select(func.count(Intelligence.id)).where(
                Intelligence.analyzed_at >= start_dt,
                Intelligence.analyzed_at <= end_dt,
                Intelligence.priority_level == "P0",
            )
        )
        p0_count = p0_result.scalar() or 0

        p1_result = await session.execute(
            select(func.count(Intelligence.id)).where(
                Intelligence.analyzed_at >= start_dt,
                Intelligence.analyzed_at <= end_dt,
                Intelligence.priority_level == "P1",
            )
        )
        p1_count = p1_result.scalar() or 0

        # Top categories
        cat_result = await session.execute(
            select(Intelligence.primary_category, func.count(Intelligence.id).label("cnt"))
            .where(
                Intelligence.analyzed_at >= start_dt,
                Intelligence.analyzed_at <= end_dt,
                Intelligence.primary_category.isnot(None),
            )
            .group_by(Intelligence.primary_category)
            .order_by(func.count(Intelligence.id).desc())
            .limit(10)
        )
        top_categories = {row[0] or "unknown": row[1] for row in cat_result}

        # Active events
        event_result = await session.execute(
            select(func.count(SecurityEvent.id)).where(
                SecurityEvent.status == "developing",
            )
        )
        active_events = event_result.scalar() or 0

    return {
        "report_type": report_type,
        "period_start": start_dt.isoformat(),
        "period_end": end_dt.isoformat(),
        "intel_count": len(top_items),
        "top_items": top_items,
        "stats": {
            "total_collected": total_collected,
            "p0_count": p0_count,
            "p1_count": p1_count,
            "top_categories": top_categories,
            "active_events": active_events,
        },
    }


async def save_and_distribute(
    *,
    ctx: Any = None,
    report_type: str,
    content: dict,
    report_data: dict,
    pdf_bytes: bytes | None = None,
    html_bytes: bytes | None = None,
) -> dict:
    """Save the generated report, archive artifacts to MinIO, trigger push.

    PDF / HTML bytes, when present, are uploaded to MinIO via
    `safe_put_report`. The returned object key is stored on
    `Report.pdf_path`. MinIO outages do NOT block DB persistence —
    `safe_put_report` absorbs CircuitOpenError and returns None.
    """
    from sia.common.minio_client import safe_put_report
    from sia.config import get_settings

    async with get_db_context() as session:
        stats = report_data.get("stats", {})
        report = Report(
            title=f"{report_type.capitalize()} Security Intelligence Report",
            report_type=report_type,
            report_version="executive",
            report_date=datetime.now().date(),
            content_json=content,
            period_start=datetime.fromisoformat(report_data["period_start"]),
            period_end=datetime.fromisoformat(report_data["period_end"]),
            intel_total=stats.get("total_collected", 0),
            intel_selected=report_data.get("intel_count", 0),
            p0_count=stats.get("p0_count", 0),
            p1_count=stats.get("p1_count", 0),
            status="generated",
            approval_status="auto_approved",
            generated_at=datetime.now(),
        )
        session.add(report)
        await session.flush()
        report_id = report.id

        # Map intelligence items to report
        for item in report_data.get("top_items", []):
            session.add(ReportIntelMap(
                report_id=report_id,
                intel_id=item["id"],
            ))

    # Archive to MinIO (best-effort; outside the DB tx to avoid holding locks
    # on network IO)
    if get_settings().minio.enabled and (pdf_bytes or html_bytes):
        object_key = None
        if pdf_bytes:
            object_key = await safe_put_report(
                report_id=report_id, report_type=report_type,
                content_bytes=pdf_bytes, content_type="application/pdf",
            )
        elif html_bytes:
            object_key = await safe_put_report(
                report_id=report_id, report_type=report_type,
                content_bytes=html_bytes, content_type="text/html",
            )
        if object_key:
            # Second small tx to update pdf_path; keeps the main tx snappy
            from sqlalchemy import update as sql_update
            async with get_db_context() as session:
                await session.execute(
                    sql_update(Report)
                    .where(Report.id == report_id)
                    .values(pdf_path=object_key)
                )

    # Publish push task
    await publish_to_stream(STREAM_PUSH_TASK, {
        "report_id": str(report_id),
        "report_type": report_type,
        "priority": "high" if report_data["stats"]["p0_count"] > 0 else "normal",
    })

    logger.info("Report saved and distribution triggered: id=%d type=%s", report_id, report_type)
    return {"report_id": report_id, "status": "distributed"}
