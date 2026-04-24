"""Executive briefing builder — layered format, headline-first.

Design goals (ARCHITECTURE_REVIEW §C9 + user requirement):
  Layer 1:  TL;DR card — 3-5 bullet points, ≤ 30 seconds reading time.
  Layer 2:  Threat Landscape Radar — P0/P1 counts, top categories, delta vs avg.
  Layer 3:  Top-3 Intelligence Spotlights — each with So-What + Action.
  Layer 4:  Strategic Recommendations — prioritized, owner-addressable.
  Layer 5:  Appendix — full item list with deep links.

The output is both:
  * `ExecBriefData`  — structured payload for template rendering
  * HTML via Jinja2 (`templates/exec_brief.html.j2`)
  * PDF via WeasyPrint (called by reporter.service)

The business aggregates (`build_brief`) reads the last period's
`intelligence` + `llm_analysis` rows and produces the layered view.

All LLM summarization calls go through the existing LLM Gateway + failover
chain; they never block report generation — on LLM outage, we fall back
to a deterministic template-only brief that still conveys counts & links.
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


# ─── Structured brief ─────────────────────────────────────────────────────

@dataclass
class IntelSpotlight:
    """One prominent item on the exec radar, with human-friendly framing."""
    intel_id: int
    title: str
    priority: str                    # P0 | P1 | P2
    category: str
    cve_id: str | None = None
    cvss_score: float | None = None
    source: str = ""
    so_what: str = ""                # "Why the exec should care" sentence
    recommended_action: str = ""     # "What to do in the next 48h"
    url: str | None = None


@dataclass
class ThreatRadar:
    """Quantitative snapshot over the reporting window."""
    window_start: datetime
    window_end: datetime
    total_collected: int
    total_after_dedup: int
    p0_count: int
    p1_count: int
    p2_count: int
    p3_count: int
    top_categories: list[tuple[str, int]]   # [(cat, count), ...] top-5
    top_affected_vendors: list[tuple[str, int]]
    kev_count: int                    # in CISA KEV
    zero_day_count: int               # flagged by LLM as 0-day
    # Deltas vs 14-day rolling average for signal-vs-noise framing
    p0_p1_delta_pct: float = 0.0
    total_delta_pct: float = 0.0


@dataclass
class ExecBriefData:
    """Full payload for the exec brief template."""
    report_id: int
    report_type: str                 # "daily" | "weekly"
    generated_at: datetime

    # Layer 1
    tldr_bullets: list[str]

    # Layer 2
    radar: ThreatRadar

    # Layer 3
    spotlights: list[IntelSpotlight] = field(default_factory=list)

    # Layer 4
    recommendations: list[dict[str, str]] = field(default_factory=list)
    # each: {"priority": "urgent|this_week|next_sprint",
    #        "text": "...",
    #        "owner": "SOC|IT Ops|AppSec|..."}

    # Layer 5 — full item list (rendered only in appendix / web)
    full_items: list[dict[str, Any]] = field(default_factory=list)

    # Meta
    company_name: str = "Our Company"
    report_version: str = "executive"
    tlp: str = "AMBER"
    window_hours: int = 24


# ─── Builder ──────────────────────────────────────────────────────────────

async def build_brief(
    *,
    report_type: str = "daily",
    window_hours: int | None = None,
    company_name: str = "Our Company",
    ctx: Any = None,
) -> ExecBriefData:
    """Aggregate recent intelligence into a layered executive briefing.

    Reads: MySQL `intelligence` + `llm_analysis` (last window).
    Writes: nothing; caller persists through reporter.save_and_distribute.
    """
    from sqlalchemy import and_, desc, func, select

    from sia.common.database import get_db_context
    from sia.models.intelligence import Intelligence

    if window_hours is None:
        window_hours = {"daily": 24, "weekly": 168, "monthly": 720}.get(report_type, 24)
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(hours=window_hours)

    async with get_db_context() as session:
        # All items in window
        items_q = (
            select(Intelligence)
            .where(and_(
                Intelligence.collected_at >= start_dt,
                Intelligence.collected_at < end_dt,
                Intelligence.processing_status.in_(("analyzed", "reviewed",
                                                     "emergency_dispatched")),
            ))
            .order_by(desc(Intelligence.total_score))
        )
        rows = (await session.execute(items_q)).scalars().all()

        # 14-day rolling baseline (for delta framing in the radar)
        baseline_start = end_dt - timedelta(days=14)
        base_count = (await session.execute(
            select(func.count(Intelligence.id))
            .where(and_(Intelligence.collected_at >= baseline_start,
                        Intelligence.collected_at < start_dt))
        )).scalar_one()
        base_p0_p1 = (await session.execute(
            select(func.count(Intelligence.id))
            .where(and_(
                Intelligence.collected_at >= baseline_start,
                Intelligence.collected_at < start_dt,
                Intelligence.priority_level.in_(("P0", "P1")),
            ))
        )).scalar_one()

    # ─── Compute radar ──────────────────────────────────────────────
    priority_counter = Counter(r.priority_level or "P3" for r in rows)
    category_counter = Counter((r.primary_category or "uncategorized") for r in rows)
    kev_count = sum(1 for r in rows if getattr(r, "is_kev", False))
    vendor_counter: Counter[str] = Counter()
    for r in rows:
        for v in (getattr(r, "affected_products", None) or []):
            if isinstance(v, dict) and (ven := v.get("vendor")):
                vendor_counter[ven] += 1

    def pct_delta(current: int, baseline: int, days_in_baseline: int = 14) -> float:
        """current vs baseline per-day rate. +50% = 1.5× the 14-day average."""
        if days_in_baseline <= 0 or baseline == 0:
            return 0.0
        baseline_per_day = baseline / days_in_baseline
        expected = baseline_per_day * max(window_hours / 24.0, 0.5)
        if expected == 0:
            return 0.0
        return round((current - expected) / expected * 100.0, 1)

    radar = ThreatRadar(
        window_start=start_dt,
        window_end=end_dt,
        total_collected=len(rows),
        total_after_dedup=len(rows),
        p0_count=priority_counter.get("P0", 0),
        p1_count=priority_counter.get("P1", 0),
        p2_count=priority_counter.get("P2", 0),
        p3_count=priority_counter.get("P3", 0),
        top_categories=category_counter.most_common(5),
        top_affected_vendors=vendor_counter.most_common(5),
        kev_count=kev_count,
        zero_day_count=sum(1 for r in rows
                           if "zero-day" in (r.primary_category or "").lower()
                           or "0day" in (r.primary_category or "").lower()),
        p0_p1_delta_pct=pct_delta(priority_counter.get("P0", 0)
                                  + priority_counter.get("P1", 0),
                                  base_p0_p1),
        total_delta_pct=pct_delta(len(rows), base_count),
    )

    # ─── Top-3 spotlights ──────────────────────────────────────────
    spotlights: list[IntelSpotlight] = []
    for r in rows[:3]:
        spot = _render_spotlight(r)
        spotlights.append(spot)

    # ─── Recommendations ───────────────────────────────────────────
    recs = _build_recommendations(radar, spotlights)

    # ─── TL;DR (4-5 sharp bullets) ─────────────────────────────────
    tldr = _build_tldr(radar, spotlights)

    # ─── Full items for appendix ──────────────────────────────────
    full = [{
        "id": r.id,
        "title": r.title,
        "priority": r.priority_level,
        "category": r.primary_category,
        "cve": r.cve_id,
        "cvss": float(r.cvss_score) if r.cvss_score else None,
        "total_score": float(r.total_score) if r.total_score else None,
        "url": r.url,
        "source": r.source_name,
    } for r in rows]

    return ExecBriefData(
        report_id=0,    # set by caller after DB insert
        report_type=report_type,
        generated_at=end_dt,
        tldr_bullets=tldr,
        radar=radar,
        spotlights=spotlights,
        recommendations=recs,
        full_items=full,
        company_name=company_name,
        window_hours=window_hours,
    )


def _render_spotlight(intel) -> IntelSpotlight:
    """Extract a human framing from an Intelligence row's LLM fields.

    Uses llm_comment / llm_impact / llm_action when present; falls back to
    deterministic templates when LLM analysis was unavailable.
    """
    so_what = (intel.llm_impact or "").strip() or (
        f"Score {intel.total_score}; "
        f"CVSS {intel.cvss_score}. Evaluate exposure in our asset inventory."
        if intel.cvss_score else
        "Evaluate relevance against our asset inventory this week."
    )
    action = (intel.llm_action or "").strip() or (
        "SOC lead to confirm whether any internal asset matches the affected products."
    )
    return IntelSpotlight(
        intel_id=intel.id,
        title=intel.title[:200],
        priority=intel.priority_level or "P2",
        category=intel.primary_category or "uncategorized",
        cve_id=intel.cve_id,
        cvss_score=float(intel.cvss_score) if intel.cvss_score else None,
        source=intel.source_name or "",
        so_what=so_what[:400],
        recommended_action=action[:400],
        url=intel.url,
    )


def _build_recommendations(
    radar: ThreatRadar, spotlights: list[IntelSpotlight]
) -> list[dict[str, str]]:
    """Deterministic strategic recs distilled from the radar.

    Pattern: if-and-only-if the data supports it, generate a concrete rec
    with owner + timeline. We avoid generic "improve security" fluff.
    """
    recs: list[dict[str, str]] = []

    if radar.kev_count > 0:
        recs.append({
            "priority": "urgent",
            "owner": "SOC + IT Ops",
            "text": f"{radar.kev_count} items in CISA KEV this period — apply vendor patches "
                    "or compensating controls within 24h per BOD 22-01.",
        })
    if radar.p0_count > 0:
        recs.append({
            "priority": "urgent",
            "owner": "CISO staff",
            "text": f"{radar.p0_count} P0 items. Convene the incident channel; "
                    "the spotlighted items (see §3) are the concrete dispositions.",
        })
    if radar.p0_p1_delta_pct > 50:
        recs.append({
            "priority": "this_week",
            "owner": "Threat Intel lead",
            "text": f"Critical + High volume is {radar.p0_p1_delta_pct:+.0f}% vs 14-day "
                    "baseline. Re-confirm subscription coverage + dedup thresholds.",
        })
    if radar.zero_day_count > 0:
        recs.append({
            "priority": "urgent",
            "owner": "AppSec + SOC",
            "text": f"{radar.zero_day_count} potential 0-days detected. Engage vendor + "
                    "review internal exposure; treat as assume-breach until patched.",
        })
    if any(v[0] and v[1] >= 3 for v in radar.top_affected_vendors):
        top_v = radar.top_affected_vendors[0]
        recs.append({
            "priority": "this_week",
            "owner": "IT Ops",
            "text": f"Recurring vendor '{top_v[0]}' ({top_v[1]} items). Audit our "
                    "deployed version + patch cadence for this vendor.",
        })
    # Always end with a continuous-improvement rec
    recs.append({
        "priority": "next_sprint",
        "owner": "Threat Intel",
        "text": "Review this brief with the SOC team; mark any item as 'not applicable' "
                "to calibrate future relevance scoring.",
    })
    return recs


def _build_tldr(radar: ThreatRadar, spotlights: list[IntelSpotlight]) -> list[str]:
    """Headline-first, maximum 5 bullets."""
    out: list[str] = []
    sign = ("📈" if radar.total_delta_pct > 0 else
            "📉" if radar.total_delta_pct < 0 else "➡️")
    out.append(
        f"{sign} {radar.total_collected} items collected "
        f"(P0: {radar.p0_count} · P1: {radar.p1_count} · KEV: {radar.kev_count}); "
        f"volume {radar.total_delta_pct:+.0f}% vs 14-day baseline."
    )
    if radar.p0_count + radar.p1_count > 0:
        top_cats = ", ".join(c for c, _ in radar.top_categories[:3]) or "—"
        out.append(f"Top threat categories: {top_cats}.")
    for sp in spotlights[:3]:
        prefix = "🚨" if sp.priority == "P0" else "⚠️"
        cve = f" ({sp.cve_id})" if sp.cve_id else ""
        out.append(f"{prefix} {sp.priority}{cve}: {sp.title[:120]}")
    return out[:5]
