"""Priority scoring engine — combines LLM scores with rule-based overrides."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sia.models.system import ScoringConfig, ScoringOverride

logger = logging.getLogger(__name__)

# Default weights if DB config not available
DEFAULT_WEIGHTS = {
    "relevance": 0.25,
    "severity": 0.30,
    "timeliness": 0.20,
    "actionability": 0.15,
    "quality": 0.10,
}

# Priority thresholds
PRIORITY_THRESHOLDS = {
    "P0": 8.0,
    "P1": 6.0,
    "P2": 4.0,
}


async def load_scoring_weights(session: AsyncSession) -> dict[str, float]:
    """Load scoring weights from database, fall back to defaults."""
    try:
        stmt = select(ScoringConfig).where(ScoringConfig.is_active == True)
        result = await session.execute(stmt)
        configs = result.scalars().all()
        if configs:
            return {c.dimension: float(c.weight) for c in configs}
    except Exception:
        logger.warning("Failed to load scoring config from DB, using defaults")
    return DEFAULT_WEIGHTS.copy()


def compute_total_score(
    dimension_scores: dict[str, float],
    weights: dict[str, float] | None = None,
) -> float:
    """Compute weighted average score from dimension scores.

    Returns a score on the same scale as inputs (1-10).
    """
    w = weights or DEFAULT_WEIGHTS
    total = 0.0
    weight_sum = 0.0
    for dim, weight in w.items():
        score = dimension_scores.get(dim, 0.0)
        total += score * weight
        weight_sum += weight
    if weight_sum > 0:
        return round(total / weight_sum, 2)
    return 0.0


def determine_priority(total_score: float) -> str:
    """Determine priority level from total score."""
    if total_score >= PRIORITY_THRESHOLDS["P0"]:
        return "P0"
    if total_score >= PRIORITY_THRESHOLDS["P1"]:
        return "P1"
    if total_score >= PRIORITY_THRESHOLDS["P2"]:
        return "P2"
    return "P3"


async def apply_overrides(
    session: AsyncSession,
    intel_data: dict[str, Any],
    computed_priority: str,
) -> str:
    """Apply rule-based priority overrides.

    Override rules:
    - KEV + CVSS ≥ 9.0 → P0
    - Enterprise asset match + CVSS ≥ 7.0 → P0
    - Active APT campaign targeting automotive → P0
    """
    try:
        stmt = select(ScoringOverride).where(ScoringOverride.is_active == True)
        result = await session.execute(stmt)
        overrides = result.scalars().all()

        for override in overrides:
            if _matches_override(override, intel_data):
                new_level = override.override_level
                if _is_higher_priority(new_level, computed_priority):
                    logger.info(
                        "Priority override applied: %s → %s (rule: %s)",
                        computed_priority, new_level, override.rule_name,
                    )
                    computed_priority = new_level
    except Exception:
        logger.exception("Failed to apply scoring overrides")

    # Hardcoded critical overrides (defense in depth)
    if intel_data.get("is_kev") and (intel_data.get("cvss_score") or 0) >= 9.0:
        if _is_higher_priority("P0", computed_priority):
            computed_priority = "P0"

    return computed_priority


def _matches_override(override: Any, intel_data: dict) -> bool:
    """Check if an override rule matches the intelligence data."""
    cond_type = override.condition_type
    cond_value = override.condition_value

    if cond_type == "cve_in_kev" and intel_data.get("is_kev"):
        return True
    if cond_type == "cvss_gte" and (intel_data.get("cvss_score") or 0) >= cond_value.get("threshold", 10):
        return True
    if cond_type == "category_match" and intel_data.get("category") in cond_value.get("categories", []):
        return True
    if cond_type == "asset_match" and intel_data.get("asset_match"):
        return True
    return False


_PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


def _is_higher_priority(new: str, current: str) -> bool:
    return _PRIORITY_ORDER.get(new, 99) < _PRIORITY_ORDER.get(current, 99)
