#!/usr/bin/env python3
"""Seed default scoring configuration and priority overrides."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from sia.common.database import get_db_context, init_db, close_db  # noqa: E402
from sia.models.system import ScoringConfig, ScoringOverride  # noqa: E402

SCORING_WEIGHTS = [
    {"dimension": "relevance", "weight": 0.25, "scoring_rules": {"description": "Relevance to automotive security"}},
    {"dimension": "severity", "weight": 0.30, "scoring_rules": {"description": "Threat/vulnerability severity"}},
    {"dimension": "timeliness", "weight": 0.20, "scoring_rules": {"description": "Time-sensitivity"}},
    {"dimension": "actionability", "weight": 0.15, "scoring_rules": {"description": "How actionable for sec team"}},
    {"dimension": "quality", "weight": 0.10, "scoring_rules": {"description": "Intelligence quality/reliability"}},
]

OVERRIDES = [
    {
        "rule_name": "KEV + Critical CVSS",
        "condition_type": "cve_in_kev",
        "condition_value": {"cvss_gte": 9.0},
        "override_level": "P0",
        "created_by": "system",
    },
    {
        "rule_name": "Enterprise Asset + High CVSS",
        "condition_type": "asset_match",
        "condition_value": {"cvss_gte": 7.0},
        "override_level": "P0",
        "created_by": "system",
    },
    {
        "rule_name": "APT targeting automotive",
        "condition_type": "category_match",
        "condition_value": {"categories": ["apt"], "industries": ["automotive"]},
        "override_level": "P0",
        "created_by": "system",
    },
]


async def main() -> None:
    await init_db()

    async with get_db_context() as session:
        for w in SCORING_WEIGHTS:
            session.add(ScoringConfig(**w, is_active=True, version=1))
        for o in OVERRIDES:
            session.add(ScoringOverride(**o, is_active=True))

    await close_db()
    print(f"Seeded {len(SCORING_WEIGHTS)} scoring configs and {len(OVERRIDES)} overrides.")


if __name__ == "__main__":
    asyncio.run(main())
