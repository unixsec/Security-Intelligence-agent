"""The Hacker News RSS (news.ycombinator.com + thehackernews.com)."""

from __future__ import annotations

from sia.adapters.collector.base import collector_registry
from sia.adapters.collector.rss import RSSCollector


@collector_registry.register("hackernews")
class HackerNewsCollector(RSSCollector):
    """Config::
        kind: hackernews
        url: https://feeds.feedburner.com/TheHackersNews
    """
    min_interval_sec = 1800
