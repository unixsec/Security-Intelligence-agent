# ================================================================
# 安全情报分析智能体 — 360 搜索 API 封装
# 版本：v1.0
# 作者：alex (unix_sec@163.com)
# 日期：2026-03-04
# ================================================================

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

import requests

logger = logging.getLogger(__name__)

# 360 搜索 API 基础配置
_SEARCH_API_BASE = "https://opensearch.360.cn/websearch/web/q"
_DEFAULT_RESULTS_PER_QUERY = 10
_REQUEST_TIMEOUT = 20
_RATE_LIMIT_SLEEP = 1.5  # 每次请求间隔（秒），避免触发限流


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    published_at: Optional[datetime] = None
    source_name: str = ""
    extra: dict = field(default_factory=dict)


class Search360Client:
    """360 搜索 API 客户端。"""

    def __init__(self, api_key: str):
        self._api_key = api_key
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "SecurityIntelAgent/1.0",
        })

    def search(
        self,
        keyword: str,
        num_results: int = _DEFAULT_RESULTS_PER_QUERY,
        date_range: str = "d7",  # 近 7 天
    ) -> List[SearchResult]:
        """
        执行关键词搜索，返回搜索结果列表。

        Args:
            keyword: 搜索关键词
            num_results: 返回结果数量（最大 10）
            date_range: 时间范围（d1=1天, d7=7天, d30=30天）

        Returns:
            SearchResult 列表
        """
        params = {
            "query": keyword,
            "num": min(num_results, 10),
            "dateRange": date_range,
            "type": "web",
        }

        try:
            resp = self._session.get(
                _SEARCH_API_BASE,
                params=params,
                timeout=_REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            return self._parse_results(data)
        except requests.RequestException as e:
            logger.warning("360 Search API error for '%s': %s", keyword, e)
            return []
        finally:
            time.sleep(_RATE_LIMIT_SLEEP)

    def _parse_results(self, data: dict) -> List[SearchResult]:
        """解析 360 搜索 API 响应。"""
        results = []
        items = data.get("items", data.get("results", []))
        for item in items:
            title = item.get("title", "").strip()
            url = item.get("url", item.get("link", "")).strip()
            snippet = item.get("description", item.get("snippet", "")).strip()

            if not title or not url:
                continue

            published_at = None
            date_str = item.get("pubdate", item.get("date", ""))
            if date_str:
                published_at = _parse_date(date_str)

            results.append(SearchResult(
                title=title,
                url=url,
                snippet=snippet,
                published_at=published_at,
                source_name=_extract_domain(url),
            ))

        return results


def _extract_domain(url: str) -> str:
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc
    except Exception:
        return ""


def _parse_date(s: str) -> Optional[datetime]:
    formats = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d"]
    for fmt in formats:
        try:
            return datetime.strptime(s[:19], fmt)
        except (ValueError, TypeError):
            continue
    return None
