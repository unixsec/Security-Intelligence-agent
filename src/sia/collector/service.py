"""Collector service — orchestrates source fetching, dedup, and ingestion."""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import select

from sia.common.database import get_db_context
from sia.common.redis import STREAM_RAW_INTEL, publish_to_stream
from sia.analyzer.dedup import check_fingerprint_exists, compute_fingerprint
from sia.collector.fetcher import RawIntelItem, create_fetcher
from sia.models.intelligence import Intelligence
from sia.models.source import IntelSource
from sia.models.system import AuditLog

logger = logging.getLogger(__name__)


async def collect_from_source(source_config: dict) -> int:
    """Collect intelligence from a single source.

    Returns the number of new items ingested.
    """
    fetcher = create_fetcher(source_config)
    items = await fetcher.fetch()
    ingested = 0

    for item in items:
        try:
            was_new = await _ingest_item(item)
            if was_new:
                ingested += 1
        except Exception:
            logger.exception("Failed to ingest item: %s", item.title[:80])

    logger.info(
        "Collection complete: source=%s fetched=%d ingested=%d",
        source_config.get("name"), len(items), ingested,
    )
    return ingested


async def _ingest_item(item: RawIntelItem) -> bool:
    """Ingest a single item: dedup check → persist → publish to stream.

    Returns True if the item was new and ingested.
    """
    fingerprint = item.fingerprint

    async with get_db_context() as session:
        # Level 1 dedup: fingerprint check
        if await check_fingerprint_exists(session, fingerprint):
            logger.debug("Duplicate skipped (fingerprint): %s", item.title[:60])
            return False

        # Create intelligence record
        intel = Intelligence(
            title=item.title,
            content=item.content,
            url=item.url,
            published_at=item.published_at,
            source_id=item.source_id,
            source_name=item.source_name,
            author=item.author,
            language=item.language,
            fingerprint=fingerprint,
            processing_status="raw",
            collected_at=datetime.now(),
            cve_id=item.extra.get("cve_id"),
            is_kev=item.extra.get("is_kev", False),
        )
        session.add(intel)
        await session.flush()
        intel_id = intel.id

    # Publish to raw_intel_stream for analysis
    await publish_to_stream(STREAM_RAW_INTEL, {
        "intel_id": str(intel_id),
        "source_name": item.source_name,
        "priority_hint": "high" if item.extra.get("is_kev") else "normal",
    })

    logger.info("Ingested intel: id=%d title=%s", intel_id, item.title[:60])
    return True


async def collect_all_sources() -> dict[str, int]:
    """Collect from all active sources. Returns source_name → count mapping."""
    results: dict[str, int] = {}

    source_configs: list[dict] = []
    async with get_db_context() as session:
        stmt = select(IntelSource).where(IntelSource.status == "active")
        result = await session.execute(stmt)
        for source in result.scalars().all():
            source_configs.append({
                "id": source.id,
                "name": source.name,
                "type": source.source_type,
                "url": source.url,
                "proxy": None,
                "timeout_seconds": source.fetch_timeout or 30,
                "parser": source.api_config.get("parser") if source.api_config else "generic",
                "headers": source.custom_headers or {},
                "api_key": source.api_config.get("api_key") if source.api_config else None,
            })

    for source_config in source_configs:
        name = source_config["name"]
        try:
            count = await collect_from_source(source_config)
            results[name] = count
        except Exception:
            logger.exception("Collection failed for source: %s", name)
            results[name] = -1

    total = sum(v for v in results.values() if v > 0)
    logger.info("Collection cycle complete: sources=%d total_new=%d", len(results), total)
    return results
