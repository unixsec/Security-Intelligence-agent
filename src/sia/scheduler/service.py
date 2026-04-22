"""Scheduler service — APScheduler-based job management."""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from sia.scheduler.jobs import (
    job_cleanup_old_data,
    job_collect_all,
    job_daily_report,
    job_weekly_report,
)

logger = logging.getLogger(__name__)


def create_scheduler() -> AsyncIOScheduler:
    """Create and configure the APScheduler instance."""
    scheduler = AsyncIOScheduler(
        job_defaults={
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": 300,
        }
    )

    # Collection: every 4 hours
    scheduler.add_job(
        job_collect_all,
        trigger=IntervalTrigger(hours=4),
        id="collect_all",
        name="Collect from all sources",
        replace_existing=True,
    )

    # Daily report: 08:00 CST (00:00 UTC)
    scheduler.add_job(
        job_daily_report,
        trigger=CronTrigger(hour=0, minute=0, timezone="UTC"),
        id="daily_report",
        name="Generate daily report",
        replace_existing=True,
    )

    # Weekly report: Monday 09:00 CST (01:00 UTC)
    scheduler.add_job(
        job_weekly_report,
        trigger=CronTrigger(day_of_week="mon", hour=1, minute=0, timezone="UTC"),
        id="weekly_report",
        name="Generate weekly report",
        replace_existing=True,
    )

    # Data cleanup: daily at 03:00 UTC
    scheduler.add_job(
        job_cleanup_old_data,
        trigger=CronTrigger(hour=3, minute=0, timezone="UTC"),
        id="cleanup_old_data",
        name="Archive old intelligence data",
        replace_existing=True,
    )

    # Note: prompt hot-reload is intentionally not scheduled. PromptManager is
    # instantiated per-consumer (see analyzer/pipeline.py::run_analysis_consumer),
    # so a scheduler-level singleton reload would not reach those instances.
    # Manual reload is still available via POST /api/v1/system/reload-prompts.

    logger.info("Scheduler configured with %d jobs", len(scheduler.get_jobs()))
    return scheduler
