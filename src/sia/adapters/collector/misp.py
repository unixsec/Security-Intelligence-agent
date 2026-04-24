"""MISP (Malware Information Sharing Platform) collector.

Config::
    kind: misp
    url: https://misp.internal/
    api_key: ...
    published_only: true
    tags: [tlp:white, circl:incident-classification="vulnerability"]
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sia.adapters.collector.base import (
    CollectorAdapter,
    RawIntelItem,
    collector_registry,
)

logger = logging.getLogger(__name__)


@collector_registry.register("misp")
class MISPCollector(CollectorAdapter):
    accepted_content_types = ("application/json",)
    min_interval_sec = 600

    async def _do(self) -> list[RawIntelItem]:
        await self._rate_gate()
        base = self.cfg.require("url", str).rstrip("/")
        api_key = self.cfg.require("api_key", str)
        since = datetime.now() - timedelta(days=self.cfg.opt("lookback_days", 7))

        body = {
            "returnFormat": "json",
            "published": self.cfg.opt("published_only", True),
            "from": since.strftime("%Y-%m-%d"),
            "limit": self.max_items,
        }
        if tags := self.cfg.opt("tags"):
            body["tags"] = tags

        headers = {"Authorization": api_key, "Accept": "application/json",
                   "Content-Type": "application/json"}
        async with self._build_http_client() as client:
            # MISP's /events/restSearch is POST
            import json as _json
            from sia.collector.url_validator import validate_source_url
            search_url = f"{base}/events/restSearch"
            validate_source_url(search_url, allowed_hosts=self.allowed_hosts)
            resp = await client.post(search_url, headers=headers, content=_json.dumps(body))
            resp.raise_for_status()
            data = resp.json()

        out: list[RawIntelItem] = []
        events = data.get("response", data if isinstance(data, list) else [])
        for wrap in events:
            e = wrap.get("Event", wrap)
            out.append(RawIntelItem(
                title=e.get("info", "MISP event")[:500],
                content=e.get("info", "") + "\n" + str(e.get("Attribute", ""))[:2000],
                url=f"{base}/events/view/{e.get('uuid') or e.get('id')}",
                published_at=self._ts(e.get("date") or e.get("timestamp")),
                source_id=self.source_id,
                source_name=self.source_name,
                extra={"misp_event_id": e.get("id"), "threat_level": e.get("threat_level_id"),
                       "tags": [t.get("name") for t in e.get("Tag", [])]},
            ))
        logger.info("misp %s: %d events", self.name, len(out))
        return out

    @staticmethod
    def _ts(s: str | int | None) -> datetime:
        if s is None:
            return datetime.now()
        try:
            # unix timestamp seconds
            return datetime.fromtimestamp(int(s))
        except (TypeError, ValueError):
            try:
                return datetime.fromisoformat(str(s))
            except ValueError:
                return datetime.now()
