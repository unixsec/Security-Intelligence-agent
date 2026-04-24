"""BleepingComputer security news RSS collector."""

from __future__ import annotations

from sia.adapters.collector.base import collector_registry
from sia.adapters.collector.rss import RSSCollector


@collector_registry.register("bleeping")
class BleepingComputerCollector(RSSCollector):
    """Config::
        kind: bleeping
        url: https://www.bleepingcomputer.com/feed/
    """
    min_interval_sec = 1800
