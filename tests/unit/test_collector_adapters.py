"""Tests for collector adapters — rate gate, registry entries, RSS parsing."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest


class TestRegistry:
    def test_all_expected_kinds_registered(self):
        from sia.adapters.collector import collector_registry
        kinds = set(collector_registry.kinds())
        expected = {
            "rss", "rest_api", "taxii", "misp", "otx", "github_advisory",
            "virustotal", "shodan", "exploit_db", "cert_eu", "jpcert",
            "cncert", "hackernews", "bleeping",
        }
        missing = expected - kinds
        assert not missing, f"missing collector kinds: {missing}"


class TestRSSCollector:
    @pytest.mark.asyncio
    async def test_parse_rss_happy(self):
        from sia.adapters.collector import collector_registry

        adapter = collector_registry.build("rss", {
            "id": 1, "name": "test",
            "url": "https://example.com/feed",
        })

        fake_xml = """<?xml version='1.0'?><rss><channel>
            <item><title>hello</title><link>https://example.com/a</link>
                  <summary>desc</summary></item>
        </channel></rss>"""

        fake_resp = type("R", (), {})()
        fake_resp.text = fake_xml
        fake_resp.content = fake_xml.encode()
        fake_resp.headers = {"content-type": "application/rss+xml"}
        fake_resp.status_code = 200
        fake_resp.is_redirect = False
        fake_resp.raise_for_status = lambda: None

        with patch.object(adapter, "_rate_gate", AsyncMock()), \
             patch.object(adapter, "_build_http_client") as bc:
            client = AsyncMock()
            client.__aenter__.return_value = client
            client.get = AsyncMock(return_value=fake_resp)
            bc.return_value = client

            with patch("sia.adapters.collector.base.validate_source_url"):
                items = await adapter.run()

        assert len(items) == 1
        assert items[0].title == "hello"
        assert items[0].url == "https://example.com/a"

    @pytest.mark.asyncio
    async def test_rate_gate_blocks_frequent(self):
        """Calling twice within cooldown: second raises AdapterError."""
        from sia.adapters.collector import collector_registry

        adapter = collector_registry.build("rss", {
            "id": 7, "name": "rate-test", "url": "https://example.com/feed",
        })
        adapter.min_interval_sec = 60

        class FakeRedis:
            def __init__(self):
                self.seen = False
            async def set(self, key, v, **kw):
                if self.seen:
                    return False
                self.seen = True
                return True

        fake = FakeRedis()
        with patch("sia.common.redis.get_redis", return_value=fake):
            # First call succeeds (bypasses parsing by raising inside _safe_get)
            from sia.adapters.base import AdapterError
            # Second call should raise rate-limited before hitting HTTP
            await adapter._rate_gate()
            with pytest.raises(AdapterError, match="rate limited"):
                await adapter._rate_gate()


class TestRESTParsers:
    def test_nvd_parser(self):
        from sia.adapters.collector.rest_api import RESTCollector
        adapter = RESTCollector({"url": "x", "parser": "nvd_cve"})
        data = {"vulnerabilities": [
            {"cve": {"id": "CVE-2026-1234", "published": "2026-04-01T00:00:00Z",
                     "descriptions": [{"lang": "en", "value": "sample desc"}],
                     "metrics": {"cvssMetricV31": [{"cvssData": {"baseScore": 9.8}}]}}},
        ]}
        items = adapter._parse_nvd(data)
        assert len(items) == 1
        assert items[0].extra["cve_id"] == "CVE-2026-1234"
        assert items[0].extra["cvss"] == 9.8

    def test_kev_parser(self):
        from sia.adapters.collector.rest_api import RESTCollector
        adapter = RESTCollector({"url": "x", "parser": "cisa_kev"})
        data = {"vulnerabilities": [
            {"cveID": "CVE-2025-9999",
             "vulnerabilityName": "Sample",
             "shortDescription": "abuse",
             "dateAdded": "2025-12-01"},
        ]}
        items = adapter._parse_kev(data)
        assert len(items) == 1
        assert items[0].extra["is_kev"] is True
        assert "CVE-2025-9999" in items[0].extra["cve_id"]

    def test_generic_parser_with_items_key(self):
        from sia.adapters.collector.rest_api import RESTCollector
        adapter = RESTCollector({"url": "x", "parser": "generic",
                                 "items_key": "entries",
                                 "title_key": "name"})
        items = adapter._parse_generic({"entries": [
            {"name": "A", "content": "c1", "url": "https://e.com/1"},
            {"name": "B", "content": "c2", "url": "https://e.com/2"},
        ]})
        assert len(items) == 2
        assert items[0].title == "A"
