"""CERT-EU publications collector (RSS subclass)."""

from __future__ import annotations

from sia.adapters.collector.base import collector_registry
from sia.adapters.collector.rss import RSSCollector


@collector_registry.register("cert_eu")
class CERTEUCollector(RSSCollector):
    """Config::
        kind: cert_eu
        url: https://cert.europa.eu/publications/threat-intelligence/rss
    """
    min_interval_sec = 3600
