"""CNCERT/CC (中国国家互联网应急中心) 公告收集器。

走 RSS 子类。内容为中文，下游 pipeline 的 language detection 会识别出 `zh`。
"""

from __future__ import annotations

from sia.adapters.collector.base import collector_registry
from sia.adapters.collector.rss import RSSCollector


@collector_registry.register("cncert")
class CNCERTCollector(RSSCollector):
    """Config::
        kind: cncert
        url: https://www.cert.org.cn/publish/main/9/index.html   # or rss endpoint
        language: zh
    """
    min_interval_sec = 3600

    def __init__(self, config, *, name=None):
        super().__init__(config, name=name)
        # Tag items as Chinese so the analyzer skips English-only language-detect
        self._lang_override = self.cfg.opt("language", "zh")

    async def _do(self):
        items = await super()._do()
        for it in items:
            it.language = self._lang_override
        return items
