"""Intelligence source fetchers — RSS, API, web scraping."""

from __future__ import annotations

import hashlib
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class RawIntelItem:
    """Standardized raw intelligence item from any source."""

    def __init__(
        self,
        title: str,
        content: str,
        url: str,
        published_at: datetime,
        source_id: int,
        source_name: str,
        *,
        author: str | None = None,
        language: str = "en",
        extra: dict | None = None,
    ):
        self.title = title
        self.content = content
        self.url = url
        self.published_at = published_at
        self.source_id = source_id
        self.source_name = source_name
        self.author = author
        self.language = language
        self.extra = extra or {}

    @property
    def fingerprint(self) -> str:
        raw = f"{self.title.strip().lower()}|{self.url.strip().lower()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class BaseFetcher(ABC):
    """Base class for all intelligence fetchers."""

    def __init__(self, source_config: dict):
        self.config = source_config
        self.source_id: int = source_config.get("id", 0)
        self.source_name: str = source_config.get("name", "unknown")
        self.timeout = source_config.get("timeout_seconds", 30)

    @abstractmethod
    async def fetch(self) -> list[RawIntelItem]:
        """Fetch intelligence items from the source."""
        ...

    async def _get_http_client(self) -> httpx.AsyncClient:
        proxy = self.config.get("proxy")
        return httpx.AsyncClient(
            timeout=self.timeout,
            proxy=proxy,
            follow_redirects=True,
            headers={"User-Agent": "SIA-Collector/1.0"},
        )


class RSSFetcher(BaseFetcher):
    """Fetch intelligence from RSS/Atom feeds."""

    async def fetch(self) -> list[RawIntelItem]:
        import feedparser

        url = self.config["url"]
        items: list[RawIntelItem] = []

        try:
            async with await self._get_http_client() as client:
                resp = await client.get(url)
                resp.raise_for_status()
                raw_text = resp.text

            feed = feedparser.parse(raw_text)
            max_items = self.config.get("max_items", 100)
            for entry in feed.entries[:max_items]:
                pub_date = datetime.now()
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    pub_date = datetime(*entry.published_parsed[:6])

                content = ""
                if hasattr(entry, "summary"):
                    content = entry.summary
                if hasattr(entry, "content") and entry.content:
                    content = entry.content[0].get("value", content)

                items.append(RawIntelItem(
                    title=entry.get("title", "No Title"),
                    content=content,
                    url=entry.get("link", url),
                    published_at=pub_date,
                    source_id=self.source_id,
                    source_name=self.source_name,
                    author=entry.get("author"),
                ))

            logger.info("RSS fetch: source=%s items=%d", self.source_name, len(items))
        except Exception:
            logger.exception("RSS fetch failed: source=%s url=%s", self.source_name, url)

        return items


class APIFetcher(BaseFetcher):
    """Fetch intelligence from REST APIs (NVD, CISA KEV, etc.)."""

    async def fetch(self) -> list[RawIntelItem]:
        url = self.config["url"]
        headers = self.config.get("headers", {})
        api_key = self.config.get("api_key")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        items: list[RawIntelItem] = []

        try:
            async with await self._get_http_client() as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()

            # Parse based on source type
            parser = self.config.get("parser", "generic")
            if parser == "nvd_cve":
                items = self._parse_nvd(data)
            elif parser == "cisa_kev":
                items = self._parse_kev(data)
            else:
                items = self._parse_generic(data)

            logger.info("API fetch: source=%s items=%d", self.source_name, len(items))
        except Exception:
            logger.exception("API fetch failed: source=%s", self.source_name)

        return items

    def _parse_nvd(self, data: dict) -> list[RawIntelItem]:
        items = []
        for vuln in data.get("vulnerabilities", []):
            cve = vuln.get("cve", {})
            cve_id = cve.get("id", "")
            descriptions = cve.get("descriptions", [])
            desc_en = next((d["value"] for d in descriptions if d["lang"] == "en"), "")

            items.append(RawIntelItem(
                title=f"{cve_id}: {desc_en[:100]}",
                content=desc_en,
                url=f"https://nvd.nist.gov/vuln/detail/{cve_id}",
                published_at=datetime.fromisoformat(
                    cve.get("published", datetime.now().isoformat()).replace("Z", "+00:00")
                ),
                source_id=self.source_id,
                source_name=self.source_name,
                extra={"cve_id": cve_id},
            ))
        return items

    def _parse_kev(self, data: dict) -> list[RawIntelItem]:
        items = []
        for vuln in data.get("vulnerabilities", []):
            cve_id = vuln.get("cveID", "")
            items.append(RawIntelItem(
                title=f"[KEV] {cve_id}: {vuln.get('vulnerabilityName', '')}",
                content=vuln.get("shortDescription", ""),
                url=f"https://nvd.nist.gov/vuln/detail/{cve_id}",
                published_at=datetime.fromisoformat(
                    vuln.get("dateAdded", datetime.now().strftime("%Y-%m-%d"))
                ),
                source_id=self.source_id,
                source_name=self.source_name,
                extra={"cve_id": cve_id, "is_kev": True},
            ))
        return items

    def _parse_generic(self, data: Any) -> list[RawIntelItem]:
        items_key = self.config.get("items_key", "items")
        title_key = self.config.get("title_key", "title")
        content_key = self.config.get("content_key", "content")
        url_key = self.config.get("url_key", "url")

        raw_items = data if isinstance(data, list) else data.get(items_key, [])
        items = []
        for item in raw_items:
            items.append(RawIntelItem(
                title=item.get(title_key, "No Title"),
                content=item.get(content_key, ""),
                url=item.get(url_key, ""),
                published_at=datetime.now(),
                source_id=self.source_id,
                source_name=self.source_name,
            ))
        return items


FETCHER_REGISTRY: dict[str, type[BaseFetcher]] = {
    "rss": RSSFetcher,
    "api": APIFetcher,
}


def create_fetcher(source_config: dict) -> BaseFetcher:
    """Factory: create a fetcher based on source type."""
    source_type = source_config.get("type", "rss")
    cls = FETCHER_REGISTRY.get(source_type)
    if cls is None:
        raise ValueError(f"Unknown source type: {source_type}")
    return cls(source_config)
