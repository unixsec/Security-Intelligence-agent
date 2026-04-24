"""Shodan monitor alerts collector."""

from __future__ import annotations

from datetime import datetime

from sia.adapters.collector.base import (
    CollectorAdapter,
    RawIntelItem,
    collector_registry,
)


@collector_registry.register("shodan")
class ShodanCollector(CollectorAdapter):
    """Pulls recent matches from a Shodan monitor (CIDR/filter saved in-console).

    Config::
        kind: shodan
        api_key: ...
        alert_id: <shodan alert id>    # optional; otherwise use query
        query: "net:<cidr>"
    """
    accepted_content_types = ("application/json",)
    min_interval_sec = 1800

    async def _do(self) -> list[RawIntelItem]:
        await self._rate_gate()
        api_key = self.cfg.require("api_key", str)
        alert_id = self.cfg.opt("alert_id")
        if alert_id:
            url = f"https://api.shodan.io/shodan/alert/{alert_id}/info?key={api_key}"
        else:
            q = self.cfg.require("query", str)
            url = f"https://api.shodan.io/shodan/host/search?key={api_key}&query={q}&limit={self.max_items}"
        async with self._build_http_client() as client:
            resp = await self._safe_get(client, url)
            data = resp.json()
        matches = data.get("matches") or data.get("triggers", {}).values() or []
        out: list[RawIntelItem] = []
        for m in matches:
            if not isinstance(m, dict):
                continue
            ip = m.get("ip_str", "")
            ports = m.get("ports") or [m.get("port")] if m.get("port") else []
            out.append(RawIntelItem(
                title=f"Shodan: {ip} ports={ports}",
                content=str(m.get("data", "") or m.get("product", ""))[:2000],
                url=f"https://www.shodan.io/host/{ip}",
                published_at=datetime.now(),
                source_id=self.source_id,
                source_name=self.source_name,
                extra={"ip": ip, "ports": ports,
                       "org": m.get("org"), "asn": m.get("asn")},
            ))
        return out
