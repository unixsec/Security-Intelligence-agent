"""Unit tests for reporter.exec_brief aggregator logic."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from sia.reporter.exec_brief import (
    ExecBriefData,
    IntelSpotlight,
    ThreatRadar,
    _build_recommendations,
    _build_tldr,
    _render_spotlight,
)


def _radar(**overrides):
    base = dict(
        window_start=datetime.now() - timedelta(hours=24),
        window_end=datetime.now(),
        total_collected=100,
        total_after_dedup=100,
        p0_count=0, p1_count=0, p2_count=40, p3_count=60,
        top_categories=[("cve", 20), ("apt", 15)],
        top_affected_vendors=[],
        kev_count=0, zero_day_count=0,
        p0_p1_delta_pct=0.0, total_delta_pct=0.0,
    )
    base.update(overrides)
    return ThreatRadar(**base)


class TestTLDR:
    def test_basic_volume_line(self):
        radar = _radar(total_collected=200, total_delta_pct=50.0)
        tldr = _build_tldr(radar, [])
        assert any("200 items" in line for line in tldr)
        assert any("+50%" in line for line in tldr)

    def test_includes_spotlights(self):
        radar = _radar(p0_count=2)
        spot = IntelSpotlight(intel_id=1, title="T", priority="P0",
                              category="cve", cve_id="CVE-2026-1")
        tldr = _build_tldr(radar, [spot])
        assert any("CVE-2026-1" in line and "P0" in line for line in tldr)

    def test_at_most_5_bullets(self):
        radar = _radar(p0_count=10)
        spots = [
            IntelSpotlight(intel_id=i, title=f"t{i}", priority="P0", category="x")
            for i in range(20)
        ]
        tldr = _build_tldr(radar, spots)
        assert len(tldr) <= 5


class TestRecommendations:
    def test_urgent_when_kev(self):
        radar = _radar(kev_count=3)
        recs = _build_recommendations(radar, [])
        assert any(r["priority"] == "urgent" and "KEV" in r["text"] for r in recs)

    def test_urgent_when_p0(self):
        radar = _radar(p0_count=2)
        recs = _build_recommendations(radar, [])
        assert any(r["priority"] == "urgent" and "P0" in r["text"] for r in recs)

    def test_volume_surge_flagged(self):
        radar = _radar(p0_p1_delta_pct=80.0)
        recs = _build_recommendations(radar, [])
        assert any("+80" in r["text"] or "80%" in r["text"] for r in recs)

    def test_recurring_vendor(self):
        radar = _radar(top_affected_vendors=[("Cisco", 5)])
        recs = _build_recommendations(radar, [])
        assert any("Cisco" in r["text"] for r in recs)

    def test_always_has_feedback_rec(self):
        """Continuous-improvement rec is always emitted."""
        recs = _build_recommendations(_radar(), [])
        assert any(r["priority"] == "next_sprint" for r in recs)


class TestSpotlightRendering:
    def test_uses_llm_fields_when_present(self):
        class Fake:
            id = 5
            title = "T"
            priority_level = "P1"
            primary_category = "cve"
            cve_id = "CVE-2026-2"
            cvss_score = 7.5
            total_score = 8.0
            source_name = "NVD"
            llm_comment = None
            llm_impact = "Affects all Windows 11"
            llm_action = "Patch within 48h"
            url = "https://x"
        sp = _render_spotlight(Fake())
        assert sp.so_what == "Affects all Windows 11"
        assert "Patch within 48h" in sp.recommended_action

    def test_fallback_when_llm_missing(self):
        class Fake:
            id = 6
            title = "T2"
            priority_level = "P2"
            primary_category = None
            cve_id = None
            cvss_score = 5.3
            total_score = 5.5
            source_name = "src"
            llm_comment = None
            llm_impact = None
            llm_action = None
            url = None
        sp = _render_spotlight(Fake())
        # Deterministic fallback template
        assert sp.so_what != ""
        assert sp.recommended_action != ""
        assert "CVSS 5.3" in sp.so_what or "5.3" in sp.so_what
