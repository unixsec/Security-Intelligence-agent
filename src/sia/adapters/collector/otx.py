"""AlienVault OTX (Open Threat Exchange) collector.

Public API: https://otx.alienvault.com/api/v1/pulses/subscribed

Config::
    kind: otx
    api_key: ...
    lookback_hours: 24
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


@collector_registry.register("otx")
class OTXCollector(CollectorAdapter):
    accepted_content_types = ("application/json",)
    min_interval_sec = 3600

    async def _do(self) -> list[RawIntelItem]:
        await self._rate_gate()
        api_key = self.cfg.require("api_key", str)
        hours = self.cfg.opt("lookback_hours", 24)
        modified_since = (datetime.now() - timedelta(hours=hours)).isoformat()
        url = (
            "https://otx.alienvault.com/api/v1/pulses/subscribed"
            f"?modified_since={modified_since}&limit={self.max_items}"
        )
        headers = {"X-OTX-API-KEY": api_key}

        async with self._build_http_client() as client:
            resp = await self._safe_get(client, url, headers=headers)
            data = resp.json()

        out: list[RawIntelItem] = []
        for p in data.get("results", []):
            out.append(RawIntelItem(
                title=p.get("name", "OTX pulse")[:500],
                content=p.get("description", "") + "\n"
                        + ", ".join(p.get("tags", []))[:2000],
                url=f"https://otx.alienvault.com/pulse/{p.get('id')}",
                published_at=self._ts(p.get("modified") or p.get("created")),
                source_id=self.source_id,
                source_name=self.source_name,
                extra={"pulse_id": p.get("id"),
                       "adversary": p.get("adversary"),
                       "industries": p.get("industries"),
                       "malware_families": p.get("malware_families")},
            ))
        logger.info("otx %s: %d pulses", self.name, len(out))
        return out

    @staticmethod
    def _ts(s: str | None) -> datetime:
        if not s:
            return datetime.now()
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return datetime.now()
