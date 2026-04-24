"""Generic REST/JSON collector with NVD + CISA KEV parsers."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sia.adapters.collector.base import (
    CollectorAdapter,
    RawIntelItem,
    collector_registry,
)

logger = logging.getLogger(__name__)


@collector_registry.register("rest_api")
class RESTCollector(CollectorAdapter):
    """Collector for JSON REST endpoints.

    Config::
        kind: rest_api
        url: https://services.nvd.nist.gov/rest/json/cves/2.0
        parser: nvd_cve    # one of: nvd_cve, cisa_kev, generic
        api_key: ...       # optional Bearer
        headers: {X-Api-Key: ...}
        items_key: vulnerabilities      # generic parser
    """

    accepted_content_types = ("application/json",)
    min_interval_sec = 600  # 10 min

    async def _do(self) -> list[RawIntelItem]:
        await self._rate_gate()
        url = self.cfg.require("url", str)
        headers = dict(self.cfg.opt("headers", {}))
        if api_key := self.cfg.opt("api_key"):
            headers.setdefault("Authorization", f"Bearer {api_key}")

        async with self._build_http_client() as client:
            resp = await self._safe_get(client, url, headers=headers)
            data = resp.json()

        parser = self.cfg.opt("parser", "generic")
        if parser == "nvd_cve":
            items = self._parse_nvd(data)
        elif parser == "cisa_kev":
            items = self._parse_kev(data)
        else:
            items = self._parse_generic(data)
        logger.info("rest_api %s(%s): %d items", self.name, parser, len(items))
        return items[: self.max_items]

    # ─── parsers ────────────────────────────────────────────────────

    def _parse_nvd(self, data: dict) -> list[RawIntelItem]:
        out: list[RawIntelItem] = []
        for vuln in data.get("vulnerabilities", []):
            cve = vuln.get("cve", {})
            cve_id = cve.get("id", "")
            descs = cve.get("descriptions", [])
            desc_en = next((d["value"] for d in descs if d.get("lang") == "en"), "")
            out.append(RawIntelItem(
                title=f"{cve_id}: {desc_en[:100]}",
                content=desc_en,
                url=f"https://nvd.nist.gov/vuln/detail/{cve_id}",
                published_at=self._parse_iso(cve.get("published")),
                source_id=self.source_id,
                source_name=self.source_name,
                extra={"cve_id": cve_id,
                       "cvss": (cve.get("metrics") or {}).get("cvssMetricV31", [{}])[0]
                                 .get("cvssData", {}).get("baseScore")},
            ))
        return out

    def _parse_kev(self, data: dict) -> list[RawIntelItem]:
        out: list[RawIntelItem] = []
        for vuln in data.get("vulnerabilities", []):
            cve_id = vuln.get("cveID", "")
            out.append(RawIntelItem(
                title=f"[KEV] {cve_id}: {vuln.get('vulnerabilityName', '')}",
                content=vuln.get("shortDescription", ""),
                url=f"https://nvd.nist.gov/vuln/detail/{cve_id}",
                published_at=self._parse_iso(vuln.get("dateAdded")),
                source_id=self.source_id,
                source_name=self.source_name,
                extra={"cve_id": cve_id, "is_kev": True,
                       "due_date": vuln.get("dueDate")},
            ))
        return out

    def _parse_generic(self, data: Any) -> list[RawIntelItem]:
        items_key = self.cfg.opt("items_key", "items")
        title_key = self.cfg.opt("title_key", "title")
        content_key = self.cfg.opt("content_key", "content")
        url_key = self.cfg.opt("url_key", "url")
        raw = data if isinstance(data, list) else data.get(items_key, [])
        out: list[RawIntelItem] = []
        for item in raw:
            out.append(RawIntelItem(
                title=str(item.get(title_key, "No Title"))[:500],
                content=str(item.get(content_key, "")),
                url=str(item.get(url_key, "")) or self.cfg.require("url"),
                published_at=self._parse_iso(item.get("published") or item.get("date")),
                source_id=self.source_id,
                source_name=self.source_name,
            ))
        return out

    @staticmethod
    def _parse_iso(s: str | None) -> datetime:
        if not s:
            return datetime.now()
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return datetime.now()
