#!/usr/bin/env python3
"""Seed default intelligence sources."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from sia.common.database import get_db_context, init_db, close_db  # noqa: E402
from sia.models.source import IntelSource  # noqa: E402

DEFAULT_SOURCES = [
    {
        "name": "NVD CVE Feed",
        "name_en": "NVD CVE Feed",
        "source_type": "api",
        "url": "https://services.nvd.nist.gov/rest/json/cves/2.0?resultsPerPage=50",
        "language": "en",
        "default_category": "vulnerability",
        "reliability": "official",
        "fetch_interval": 360,
        "api_config": {"parser": "nvd_cve"},
    },
    {
        "name": "CISA KEV Catalog",
        "name_en": "CISA Known Exploited Vulnerabilities",
        "source_type": "api",
        "url": "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json",
        "language": "en",
        "default_category": "vulnerability",
        "reliability": "official",
        "fetch_interval": 720,
        "api_config": {"parser": "cisa_kev"},
    },
    {
        "name": "Krebs on Security",
        "name_en": "Krebs on Security",
        "source_type": "rss",
        "url": "https://krebsonsecurity.com/feed/",
        "language": "en",
        "default_category": "threat_actor",
        "reliability": "authority",
        "fetch_interval": 240,
    },
    {
        "name": "The Hacker News",
        "name_en": "The Hacker News",
        "source_type": "rss",
        "url": "https://feeds.feedburner.com/TheHackersNews",
        "language": "en",
        "default_category": "threat_actor",
        "reliability": "professional",
        "fetch_interval": 180,
    },
    {
        "name": "Bleeping Computer",
        "name_en": "Bleeping Computer",
        "source_type": "rss",
        "url": "https://www.bleepingcomputer.com/feed/",
        "language": "en",
        "default_category": "malware",
        "reliability": "professional",
        "fetch_interval": 180,
    },
    {
        "name": "安全客",
        "name_en": "Anquanke",
        "source_type": "rss",
        "url": "https://api.anquanke.com/data/v1/rss",
        "language": "zh",
        "default_category": "vulnerability",
        "reliability": "professional",
        "fetch_interval": 240,
    },
]


async def main() -> None:
    await init_db()

    async with get_db_context() as session:
        for source_data in DEFAULT_SOURCES:
            source = IntelSource(**source_data, status="active")
            session.add(source)
        print(f"Seeded {len(DEFAULT_SOURCES)} default sources.")

    await close_db()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
