"""Scheduled jobs — collection, report generation, maintenance.

Each job is wrapped in `with_leader_lock` so only one `sia-api` replica runs
the work when the Deployment is scaled out (ARCHITECTURE_REVIEW §B-2 / §E.2).

FN-1: daily / weekly reports flow through the full executive-briefing
pipeline (build_brief → render HTML → save_and_distribute) instead of the
v0.2 placeholder f-string. The deterministic templates inside ``exec_brief``
already handle the LLM-unavailable case, so this path is safe even when the
LLM gateway circuit is open.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import datetime

from sia.scheduler.distributed_lock import with_leader_lock

logger = logging.getLogger(__name__)


def _brief_to_jsonable(brief) -> dict:
    """``asdict()`` keeps datetime objects; convert them to isoformat for JSON."""
    import json
    return json.loads(json.dumps(asdict(brief), default=str))


@with_leader_lock("collect_all", ttl_sec=3600)
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


async def _run_briefed_report(report_type: str, window_hours: int) -> None:
    """Shared body for daily / weekly scheduled reports (FN-1).

    Flow:
      1. ``gather_report_data`` — DB aggregates for top-N + counts.
      2. Skip silently if zero intel was collected in the window.
      3. ``build_brief`` — 5-layer ExecBriefData built from MySQL rows; uses
         deterministic templates when LLM fields are absent so this never
         depends on LLM gateway availability.
      4. ``render_html`` — Jinja-rendered HTML (UTF-8 bytes).
      5. ``save_and_distribute`` — persist Report row, archive HTML to MinIO,
         publish a push task on ``push_task_stream``.
    """
    from sia.reporter.exec_brief import build_brief
    from sia.reporter.exec_render import render_html
    from sia.reporter.service import gather_report_data, save_and_distribute

    logger.info("Scheduled %s report generation started", report_type)
    try:
        report_data = await gather_report_data(report_type=report_type)
        if report_data["stats"]["total_collected"] == 0:
            logger.info("No intel collected for %s window, skipping report", report_type)
            return

        brief = await build_brief(report_type=report_type, window_hours=window_hours)
        content = _brief_to_jsonable(brief)
        try:
            html_bytes = render_html(brief).encode("utf-8")
        except Exception:
            # Template / weasyprint problems should not lose the JSON payload;
            # downstream still gets the structured brief in DB.
            logger.exception("HTML render failed for %s report; persisting JSON only", report_type)
            html_bytes = None

        await save_and_distribute(
            report_type=report_type,
            content=content,
            report_data=report_data,
            html_bytes=html_bytes,
        )
        logger.info(
            "%s report generated: items=%d P0=%d P1=%d KEV=%d",
            report_type,
            brief.radar.total_collected,
            brief.radar.p0_count,
            brief.radar.p1_count,
            brief.radar.kev_count,
        )
    except Exception:
        logger.exception("%s report generation failed", report_type)


@with_leader_lock("daily_report", ttl_sec=1800)
async def job_daily_report() -> None:
    """Scheduled job: generate daily report."""
    await _run_briefed_report("daily", window_hours=24)


@with_leader_lock("weekly_report", ttl_sec=1800)
async def job_weekly_report() -> None:
    """Scheduled job: generate weekly report."""
    await _run_briefed_report("weekly", window_hours=168)


@with_leader_lock("cleanup_old_data", ttl_sec=3600)
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
