"""Three-level deduplication: SHA256 fingerprint → vector similarity → cross-day dedup."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sia.models.intelligence import Intelligence

logger = logging.getLogger(__name__)


def compute_fingerprint(title: str, url: str) -> str:
    """Level 1: SHA256 fingerprint from title + URL."""
    raw = f"{title.strip().lower()}|{url.strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def check_fingerprint_exists(session: AsyncSession, fingerprint: str) -> bool:
    """Check if a fingerprint already exists in the database."""
    stmt = select(Intelligence.id).where(Intelligence.fingerprint == fingerprint).limit(1)
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


async def check_vector_similarity(
    milvus_client: Any,
    embedding: list[float],
    *,
    threshold: float = 0.85,
    collection_name: str = "intel_vectors",
) -> list[dict]:
    """Level 2: Vector similarity check via Milvus.

    Returns list of similar items with scores above threshold.
    """
    if milvus_client is None:
        return []

    try:
        results = milvus_client.search(
            collection_name=collection_name,
            data=[embedding],
            limit=5,
            output_fields=["intel_id", "title"],
            search_params={"metric_type": "COSINE", "params": {"nprobe": 10}},
        )
        similar = []
        for hits in results:
            for hit in hits:
                score = hit.get("distance", 0)
                if score >= threshold:
                    similar.append({
                        "intel_id": hit.get("entity", {}).get("intel_id"),
                        "title": hit.get("entity", {}).get("title"),
                        "similarity": score,
                    })
        return similar
    except Exception:
        logger.exception("Milvus similarity search failed")
        return []


async def check_cross_day_dedup(
    milvus_client: Any,
    embedding: list[float],
    *,
    threshold: float = 0.80,
    collection_name: str = "intel_vectors",
) -> list[dict]:
    """Level 3: Cross-day deduplication with lower threshold."""
    return await check_vector_similarity(
        milvus_client, embedding, threshold=threshold, collection_name=collection_name
    )
