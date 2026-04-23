"""Rebuild Milvus vectors from MySQL intelligence (ARCHITECTURE_REVIEW §C1).

When Milvus data is lost (hardware failure / upgrade mistake / no backup),
we can reconstruct the semantic-dedup index from the authoritative source:
MySQL's `intelligence` table.

This script:
  1. Streams `intelligence.id` + `content` in batches
  2. Calls the LLM Gateway's embedding API
  3. Upserts (id, vector) to Milvus

Safe to re-run; idempotent via `intel_id` primary key in Milvus.

Usage:
    python scripts/ops/rebuild_vectors.py                   # all rows
    python scripts/ops/rebuild_vectors.py --since 2026-01-01
    python scripts/ops/rebuild_vectors.py --batch 200
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


async def _main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", help="YYYY-MM-DD; only rebuild rows created >= this")
    ap.add_argument("--batch", type=int, default=100, help="batch size")
    ap.add_argument("--limit", type=int, default=None,
                    help="stop after N rows (for sanity testing)")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

    from sqlalchemy import select

    from sia.common.database import get_db_context
    from sia.config import get_llm_config, get_settings
    from sia.gateway.llm.gateway import LLMGateway
    from sia.models.intelligence import Intelligence

    settings = get_settings()
    gateway = LLMGateway(get_llm_config())

    # Milvus client — reuse sia infra if available, else skip safely
    try:
        from pymilvus import Collection, connections
    except ImportError:
        logger.error("pymilvus not installed; install to rebuild vectors")
        return 1

    connections.connect(
        alias="default",
        host=settings.milvus.host,
        port=settings.milvus.port,
        token=settings.milvus.token or None,
    )
    collection = Collection(settings.milvus.collection_name)
    logger.info("connected to milvus collection=%s",
                settings.milvus.collection_name)

    since = datetime.fromisoformat(args.since) if args.since else None
    processed = 0
    async with get_db_context() as session:
        stmt = select(Intelligence.id, Intelligence.content).order_by(Intelligence.id.asc())
        if since is not None:
            stmt = stmt.where(Intelligence.collected_at >= since)
        if args.limit:
            stmt = stmt.limit(args.limit)

        batch: list[tuple[int, str]] = []
        async for row in (await session.stream(stmt)).scalars() if False else iter([]):
            # (fall-through: sqlalchemy's async stream is slightly different; use execute + scalars)
            pass
        rows = (await session.execute(stmt)).all()

        for row_id, content in rows:
            if not content:
                continue
            batch.append((row_id, content[:8000]))  # cap content length
            if len(batch) >= args.batch:
                await _flush(gateway, collection, batch)
                processed += len(batch)
                logger.info("rebuilt %d vectors", processed)
                batch = []
        if batch:
            await _flush(gateway, collection, batch)
            processed += len(batch)

    logger.info("rebuild complete: %d vectors", processed)
    return 0


async def _flush(gateway, collection, batch: list[tuple[int, str]]) -> None:
    ids = [b[0] for b in batch]
    texts = [b[1] for b in batch]
    vectors = await gateway.embedding(texts)
    # Milvus upsert: delete+insert pattern for re-runnable behavior
    expr = f"intel_id in {ids}"
    try:
        collection.delete(expr)
    except Exception:  # noqa: BLE001 — collection may be empty on first run
        pass
    collection.insert([ids, vectors])


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(_main()))
