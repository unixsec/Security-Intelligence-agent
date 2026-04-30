"""Three-level intelligence deduplication (FN-2 / v0.4).

Levels
------
1. **SHA-256 fingerprint** of ``(title, url)`` — DB-level UK enforces it.
   Cost: ~1 ms.
2. **Same-day vector similarity** — Milvus cosine ≥ 0.85 within last 24 h
   indicates "another source covering the same incident today". The new
   item is still persisted (different feeds have different metadata) but
   marked ``related_to=<other_id>`` so the analyst UI can fold them.
3. **Cross-day vector similarity** — Milvus cosine ≥ 0.80 within last 14 d
   indicates "this story is resurfacing". Same flag mechanism, lower
   threshold, larger window.

Failure mode
------------
Every Milvus call is best-effort. If embedding fails, or Milvus is down /
disabled, levels 2/3 silently degrade to "no decision". They never *cause*
data to be dropped; level 1 is the only authoritative drop.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sia.models.intelligence import Intelligence

logger = logging.getLogger(__name__)


# ─── Level 1 ──────────────────────────────────────────────────────────────

def compute_fingerprint(title: str, url: str) -> str:
    """SHA-256 fingerprint from title + URL — the primary dedup key."""
    raw = f"{title.strip().lower()}|{url.strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def check_fingerprint_exists(session: AsyncSession, fingerprint: str) -> bool:
    """Return True iff this fingerprint already exists in ``intelligence``."""
    stmt = select(Intelligence.id).where(Intelligence.fingerprint == fingerprint).limit(1)
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


# ─── Levels 2 / 3 ────────────────────────────────────────────────────────


def _embed_intel(title: str, content: str) -> list[float] | None:
    """Embed ``title + content`` for similarity search. None when unavailable."""
    from sia.common.milvus_client import embed_text
    text = (title or "") + "\n" + (content or "")[:4000]
    return embed_text(text)


async def check_vector_similarity(
    *,
    title: str,
    content: str,
    threshold: float | None = None,
    window_hours: int = 24,
    exclude_intel_id: int | None = None,
) -> list[dict[str, Any]]:
    """Level 2 — return same-day hits whose cosine ≥ threshold.

    Args
    ----
    title, content : raw fields of the candidate item.
    threshold      : override the configured ``same_day_threshold``.
    window_hours   : limit to items collected within the last N hours.
    exclude_intel_id : when re-checking an already-persisted row, pass its
        id so it is not its own duplicate.

    Returns
    -------
    list of hit dicts with ``intel_id, title, category, similarity``,
    sorted by ``similarity`` descending. Empty when Milvus disabled or no
    embedding available.
    """
    from sia.common.milvus_client import is_enabled, search_similar
    from sia.config import get_settings

    if not is_enabled():
        return []
    embedding = _embed_intel(title, content)
    if embedding is None:
        return []

    if threshold is None:
        threshold = get_settings().milvus.same_day_threshold
    cutoff = int((datetime.now(timezone.utc) - timedelta(hours=window_hours)).timestamp())
    hits = search_similar(
        embedding,
        top_k=5,
        min_collected_at_epoch=cutoff,
        exclude_intel_id=exclude_intel_id,
    )
    return [h for h in hits if h["similarity"] >= threshold]


async def check_cross_day_dedup(
    *,
    title: str,
    content: str,
    threshold: float | None = None,
    window_days: int | None = None,
    exclude_intel_id: int | None = None,
) -> list[dict[str, Any]]:
    """Level 3 — same as level 2 but with a wider window and lower threshold.

    Catches re-surfacing of an old story (e.g. a CVE getting an exploit
    published two weeks after disclosure).
    """
    from sia.common.milvus_client import is_enabled, search_similar
    from sia.config import get_settings

    if not is_enabled():
        return []
    embedding = _embed_intel(title, content)
    if embedding is None:
        return []

    cfg = get_settings().milvus
    if threshold is None:
        threshold = cfg.cross_day_threshold
    if window_days is None:
        window_days = cfg.cross_day_window_days
    cutoff = int((datetime.now(timezone.utc) - timedelta(days=window_days)).timestamp())
    hits = search_similar(
        embedding,
        top_k=5,
        min_collected_at_epoch=cutoff,
        exclude_intel_id=exclude_intel_id,
    )
    return [h for h in hits if h["similarity"] >= threshold]


async def index_intel_vector(
    *,
    intel_id: int,
    title: str,
    content: str,
    category: str,
    collected_at: datetime,
) -> bool:
    """Persist the embedding for this intel into Milvus for future searches.

    Called after ``persist_analysis_result`` so the row is locked in. Returns
    True on success; False (and logs) on Milvus / embedding failure.
    """
    from sia.common.milvus_client import is_enabled, upsert_vector
    if not is_enabled():
        return False
    embedding = _embed_intel(title, content)
    if embedding is None:
        return False
    epoch = int(collected_at.timestamp() if collected_at else datetime.now(timezone.utc).timestamp())
    return upsert_vector(
        intel_id=intel_id,
        embedding=embedding,
        category=category,
        title=title,
        collected_at_epoch=epoch,
    )
