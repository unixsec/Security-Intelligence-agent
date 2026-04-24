"""Generic RSS/Atom collector (replaces legacy RSSFetcher)."""

from __future__ import annotations

import logging
from datetime import datetime

from sia.adapters.collector.base import (
    CollectorAdapter,
    RawIntelItem,
    collector_registry,
)

logger = logging.getLogger(__name__)


@collector_registry.register("rss")
class RSSCollector(CollectorAdapter):
    """Pulls entries from an RSS or Atom feed.

    Config::

        kind: rss
        url: https://example.com/feed.xml
        max_items: 100
        allowed_hosts: [example.com]       # optional SSRF allowlist
    """

    accepted_content_types = (
        "application/rss", "application/atom", "application/xml",
        "text/xml", "text/html",            # many feeds misconfigure CT
    )
    min_interval_sec = 300  # 5 min: polite

    async def _do(self) -> list[RawIntelItem]:
        import feedparser

        await self._rate_gate()
        url = self.cfg.require("url", str)
        items: list[RawIntelItem] = []

        async with self._build_http_client() as client:
            resp = await self._safe_get(client, url)
            raw = resp.text

        feed = feedparser.parse(raw)
        for entry in feed.entries[: self.max_items]:
            pub = datetime.now()
            if getattr(entry, "published_parsed", None):
                pub = datetime(*entry.published_parsed[:6])
            content = (
                entry.content[0].get("value") if getattr(entry, "content", None)
                else getattr(entry, "summary", "")
            )
            items.append(RawIntelItem(
                title=entry.get("title", "No Title"),
                content=content or "",
                url=entry.get("link", url),
                published_at=pub,
                source_id=self.source_id,
                source_name=self.source_name,
                author=entry.get("author"),
            ))
        logger.info("rss %s: %d items", self.name, len(items))
        return items
