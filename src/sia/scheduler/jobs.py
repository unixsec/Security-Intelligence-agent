"""Scheduled jobs — collection, report generation, maintenance."""

from __future__ import annotations

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


async def job_collect_all() -> None:
    """Scheduled job: collect from all active sources."""
    from sia.collector.service import collect_all_sources
    logger.info("Scheduled collection started")
    try:
        results = await collect_all_sources()
        total = sum(v for v in results.values() if v > 0)
        logger.info("Scheduled collection done: sources=%d new=%d", len(results), total)
    except Exception:
        logger.exception("Scheduled collection failed")


async def job_daily_report() -> None:
    """Scheduled job: generate daily report."""
    from sia.reporter.service import gather_report_data, save_and_distribute

    logger.info("Scheduled daily report generation started")
    try:
        report_data = await gather_report_data(report_type="daily")
        if report_data["stats"]["total_collected"] == 0:
            logger.info("No intel collected today, skipping report")
            return

        # Generate via LLM would happen via workflow; for scheduled job we do a simpler version
        content = {
            "executive_summary": f"Daily report: {report_data['stats']['total_collected']} items collected, "
                                 f"{report_data['stats']['p0_count']} P0, {report_data['stats']['p1_count']} P1",
            "generated_at": datetime.now().isoformat(),
        }
        await save_and_distribute(
            report_type="daily",
            content=content,
            report_data=report_data,
        )
        logger.info("Daily report generated successfully")
    except Exception:
        logger.exception("Daily report generation failed")


async def job_weekly_report() -> None:
    """Scheduled job: generate weekly report."""
    from sia.reporter.service import gather_report_data, save_and_distribute

    logger.info("Scheduled weekly report generation started")
    try:
        report_data = await gather_report_data(report_type="weekly")
        content = {
            "executive_summary": f"Weekly report: {report_data['stats']['total_collected']} items, "
                                 f"{report_data['stats']['p0_count']} P0, {report_data['stats']['p1_count']} P1",
            "generated_at": datetime.now().isoformat(),
        }
        await save_and_distribute(
            report_type="weekly",
            content=content,
            report_data=report_data,
        )
    except Exception:
        logger.exception("Weekly report generation failed")


async def job_cleanup_old_data() -> None:
    """Scheduled job: archive old data, clean up DLQ."""
    from sqlalchemy import update
    from sia.common.database import get_db_context
    from sia.models.intelligence import Intelligence
    from datetime import timedelta

    cutoff = datetime.now() - timedelta(days=90)
    logger.info("Archiving intelligence older than %s", cutoff.date())

    try:
        async with get_db_context() as session:
            result = await session.execute(
                update(Intelligence)
                .where(
                    Intelligence.collected_at < cutoff,
                    Intelligence.processing_status != "archived",
                )
                .values(processing_status="archived")
            )
            logger.info("Archived %d old intelligence records", result.rowcount)
    except Exception:
        logger.exception("Cleanup job failed")


async def job_reload_prompts() -> None:
    """Kept for backwards compatibility with the /system/reload-prompts endpoint.

    PromptManager is instantiated per-consumer (see analyzer.pipeline), so a
    process-level reload from here cannot actually refresh those instances.
    Callers should treat a successful return as 'reload signal accepted' only.
    """
    logger.info(
        "Prompt reload requested; per-consumer PromptManagers will pick up "
        "changes on the next restart or reload cycle."
    )
