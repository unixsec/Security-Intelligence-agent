"""VirusTotal Intelligence feed collector."""

from __future__ import annotations

from datetime import datetime

from sia.adapters.collector.base import (
    CollectorAdapter,
    RawIntelItem,
    collector_registry,
)


@collector_registry.register("virustotal")
class VirusTotalCollector(CollectorAdapter):
    """Pulls latest flagged files/urls via VT Intelligence search.

    Requires a VT Premium api_key with Intelligence access.
    Config::
        kind: virustotal
        api_key: ...
        query: "p:5+ type:peexe fs:72h+"
    """
    accepted_content_types = ("application/json",)
    min_interval_sec = 600

    async def _do(self) -> list[RawIntelItem]:
        await self._rate_gate()
        api_key = self.cfg.require("api_key", str)
        query = self.cfg.opt("query", "p:5+ fs:24h+")
        url = (f"https://www.virustotal.com/api/v3/intelligence/search"
               f"?query={query}&limit={min(self.max_items, 40)}")
        headers = {"x-apikey": api_key}
        async with self._build_http_client() as client:
            resp = await self._safe_get(client, url, headers=headers)
            data = resp.json()
        out: list[RawIntelItem] = []
        for d in data.get("data", []):
            attrs = d.get("attributes", {})
            sha256 = attrs.get("sha256") or d.get("id") or ""
            out.append(RawIntelItem(
                title=f"VT hit: {attrs.get('meaningful_name') or sha256[:16]} "
                      f"({attrs.get('last_analysis_stats', {}).get('malicious')} AVs)",
                content=(attrs.get("tags") or []).__str__(),
                url=f"https://www.virustotal.com/gui/file/{sha256}",
                published_at=datetime.fromtimestamp(
                    attrs.get("last_analysis_date") or attrs.get("creation_date") or 0
                ) if attrs.get("last_analysis_date") else datetime.now(),
                source_id=self.source_id,
                source_name=self.source_name,
                extra={"sha256": sha256, "type": attrs.get("type_description"),
                       "vt_stats": attrs.get("last_analysis_stats")},
            ))
        return out
