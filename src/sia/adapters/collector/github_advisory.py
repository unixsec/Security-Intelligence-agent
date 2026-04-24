"""GitHub Security Advisory (GHSA) collector via GraphQL API.

Config::
    kind: github_advisory
    api_key: ghp_...       # needs 'security_events' scope
    ecosystems: [pip, npm, maven, go, cargo, nuget, rubygems, composer]
    severity: HIGH         # optional filter: CRITICAL|HIGH|MODERATE|LOW
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

_GQL = """
query($first: Int!, $severity: [SecurityAdvisorySeverity!]) {
  securityAdvisories(first: $first, orderBy: {field: PUBLISHED_AT, direction: DESC},
                     classifications: [GENERAL], severities: $severity) {
    nodes {
      ghsaId summary description severity publishedAt permalink
      cwes(first: 5) { nodes { cweId } }
      identifiers { type value }
      vulnerabilities(first: 5) { nodes { package { ecosystem name } vulnerableVersionRange } }
    }
  }
}
"""


@collector_registry.register("github_advisory")
class GitHubAdvisoryCollector(CollectorAdapter):
    accepted_content_types = ("application/json",)
    min_interval_sec = 3600

    async def _do(self) -> list[RawIntelItem]:
        import json as _json

        await self._rate_gate()
        api_key = self.cfg.require("api_key", str)
        severities = self.cfg.opt("severities", ["CRITICAL", "HIGH"])
        url = "https://api.github.com/graphql"
        headers = {
            "Authorization": f"bearer {api_key}",
            "Accept": "application/vnd.github.v4+json",
            "Content-Type": "application/json",
        }
        payload = _json.dumps({
            "query": _GQL,
            "variables": {"first": min(self.max_items, 100), "severity": severities},
        })

        async with self._build_http_client() as client:
            from sia.collector.url_validator import validate_source_url
            validate_source_url(url, allowed_hosts=self.allowed_hosts)
            resp = await client.post(url, headers=headers, content=payload)
            resp.raise_for_status()
            body = resp.json()

        nodes = (((body.get("data") or {}).get("securityAdvisories") or {}).get("nodes")) or []
        out: list[RawIntelItem] = []
        ecos_filter = set(self.cfg.opt("ecosystems", [])) or None
        for n in nodes:
            if ecos_filter and not any(
                v["package"]["ecosystem"].lower() in ecos_filter
                for v in n.get("vulnerabilities", {}).get("nodes", [])
            ):
                continue
            cves = [i["value"] for i in n.get("identifiers", []) if i.get("type") == "CVE"]
            out.append(RawIntelItem(
                title=f"[{n['severity']}] {n['ghsaId']}: {n['summary'][:200]}",
                content=n.get("description") or "",
                url=n.get("permalink") or f"https://github.com/advisories/{n['ghsaId']}",
                published_at=self._ts(n.get("publishedAt")),
                source_id=self.source_id,
                source_name=self.source_name,
                extra={"ghsa_id": n["ghsaId"], "severity": n["severity"],
                       "cves": cves,
                       "cwes": [c["cweId"] for c in n.get("cwes", {}).get("nodes", [])]},
            ))
        logger.info("github_advisory %s: %d advisories", self.name, len(out))
        return out

    @staticmethod
    def _ts(s: str | None) -> datetime:
        if not s:
            return datetime.now()
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return datetime.now()
