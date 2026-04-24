"""TAXII 2.x STIX threat-intel collector (CISA, FIRST, MITRE, commercial feeds).

TAXII is the OASIS-standard transport for STIX 2.x objects. Most national
CERTs and major commercial TI providers expose a TAXII endpoint.

Config::

    kind: taxii
    url: https://www.cisa.gov/taxii2/api2/collections/<COLL_ID>/objects/
    api_key: ...              # optional
    stix_types: [indicator, report]   # filter by STIX object type
"""

from __future__ import annotations

import logging
from datetime import datetime

from sia.adapters.collector.base import (
    CollectorAdapter,
    RawIntelItem,
    collector_registry,
)

logger = logging.getLogger(__name__)


@collector_registry.register("taxii")
class TAXIICollector(CollectorAdapter):
    accepted_content_types = ("application/json", "application/taxii+json",
                              "application/stix+json")
    min_interval_sec = 900  # 15 min — TAXII servers are often strict

    async def _do(self) -> list[RawIntelItem]:
        await self._rate_gate()
        url = self.cfg.require("url", str)
        headers = {"Accept": "application/taxii+json;version=2.1"}
        if api_key := self.cfg.opt("api_key"):
            headers["Authorization"] = f"Bearer {api_key}"

        async with self._build_http_client() as client:
            resp = await self._safe_get(client, url, headers=headers)
            body = resp.json()

        wanted = set(self.cfg.opt("stix_types", ["indicator", "report", "vulnerability"]))
        out: list[RawIntelItem] = []
        for obj in body.get("objects", [])[: self.max_items]:
            if obj.get("type") not in wanted:
                continue
            title = obj.get("name") or obj.get("pattern") or obj["id"]
            content = obj.get("description") or obj.get("pattern") or ""
            pub = self._ts(obj.get("modified") or obj.get("created"))
            out.append(RawIntelItem(
                title=str(title)[:500],
                content=str(content),
                url=self._stix_url(obj),
                published_at=pub,
                source_id=self.source_id,
                source_name=self.source_name,
                extra={"stix_type": obj.get("type"), "stix_id": obj.get("id"),
                       "labels": obj.get("labels", [])},
            ))
        logger.info("taxii %s: %d items (filtered %d total)",
                    self.name, len(out), len(body.get("objects", [])))
        return out

    @staticmethod
    def _ts(s: str | None) -> datetime:
        if not s:
            return datetime.now()
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return datetime.now()

    def _stix_url(self, obj: dict) -> str:
        # STIX has no canonical URL; surface an Object-ID reference
        return f"stix://{obj.get('id', 'unknown')}"
