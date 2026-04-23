"""Re-queue orphaned 'analyzing' intelligence (ARCHITECTURE_REVIEW §C1).

If sia-consumer crashes mid-analysis, or Redis Streams loses pending
messages, some `intelligence.processing_status = 'analyzing'` rows will
never complete. This script finds them and re-publishes to the raw stream.

Run as a K8s CronJob every N minutes. Idempotent: re-publishing the same
intel_id makes the consumer re-analyze, which is harmless because
`analyze_intel` workflow is designed to be rerunnable (persist step does
UPDATE, not INSERT).

Usage:
    python scripts/ops/reconcile_analyzing.py --older-than 15m
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def _parse_duration(s: str) -> timedelta:
    """Parse e.g. '15m', '2h', '1d' into timedelta."""
    m = re.fullmatch(r"(\d+)([smhd])", s)
    if not m:
        raise argparse.ArgumentTypeError(f"bad duration: {s!r} (use like '15m', '2h')")
    n, u = int(m.group(1)), m.group(2)
    return {"s": timedelta(seconds=n), "m": timedelta(minutes=n),
            "h": timedelta(hours=n), "d": timedelta(days=n)}[u]


async def _main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--older-than", type=_parse_duration, default=timedelta(minutes=15),
                    help="only re-queue rows stuck for at least this long (default 15m)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=500)
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

    from sqlalchemy import select, update

    from sia.common.database import get_db_context
    from sia.common.redis import STREAM_RAW_INTEL, get_redis
    from sia.models.intelligence import Intelligence

    cutoff = datetime.now() - args.older_than
    logger.info("reconciling rows stuck analyzing since before %s", cutoff.isoformat())

    redis = get_redis()
    requeued = 0
    async with get_db_context() as session:
        rows = (await session.execute(
            select(Intelligence.id)
            .where(
                Intelligence.processing_status == "analyzing",
                Intelligence.collected_at < cutoff,
            )
            .order_by(Intelligence.id.asc())
            .limit(args.limit)
        )).scalars().all()

        logger.info("found %d orphaned analyzing rows", len(rows))
        if not rows:
            return 0

        if args.dry_run:
            logger.info("dry-run: would re-queue ids=%s", rows[:20] + (["..."] if len(rows) > 20 else []))
            return 0

        for intel_id in rows:
            try:
                await redis.xadd(STREAM_RAW_INTEL, {"intel_id": str(intel_id),
                                                    "reconciled": "true"})
                requeued += 1
            except Exception:
                logger.exception("failed to re-queue intel_id=%s", intel_id)

        # Mark them pending again so if this script ran twice we don't double-publish
        await session.execute(
            update(Intelligence)
            .where(Intelligence.id.in_(rows))
            .values(processing_status="pending")
        )

    logger.info("reconcile done: re-queued %d", requeued)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(_main()))
