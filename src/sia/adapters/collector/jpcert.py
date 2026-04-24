"""JPCERT/CC alerts collector (RSS subclass)."""

from __future__ import annotations

from sia.adapters.collector.base import collector_registry
from sia.adapters.collector.rss import RSSCollector


@collector_registry.register("jpcert")
class JPCERTCollector(RSSCollector):
    """Config::
        kind: jpcert
        url: https://www.jpcert.or.jp/english/rss/jpcert-en.rdf
    """
    min_interval_sec = 3600
