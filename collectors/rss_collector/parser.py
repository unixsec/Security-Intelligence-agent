# ================================================================
# 安全情报分析智能体 — RSS 解析器
# 版本：v1.0
# 作者：alex (unix_sec@163.com)
# 日期：2026-03-04
# ================================================================

import logging
from dataclasses import dataclass, field
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import List, Optional
from urllib.parse import urlparse

import feedparser

logger = logging.getLogger(__name__)


@dataclass
class FeedEntry:
    title: str
    link: str
    content: str
    summary: str
    published_at: Optional[datetime]
    source_name: str = ""
    extra: dict = field(default_factory=dict)


def _parse_published(entry) -> Optional[datetime]:
    """尝试从 feedparser entry 解析发布时间。"""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            return datetime(*entry.published_parsed[:6])
        except Exception:
            pass
    if hasattr(entry, "published") and entry.published:
        try:
            return parsedate_to_datetime(entry.published).replace(tzinfo=None)
        except Exception:
            pass
    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        try:
            return datetime(*entry.updated_parsed[:6])
        except Exception:
            pass
    return None


def _extract_content(entry) -> str:
    """从 feedparser entry 提取正文内容。"""
    if hasattr(entry, "content") and entry.content:
        return entry.content[0].get("value", "")
    if hasattr(entry, "summary_detail") and entry.summary_detail:
        return entry.summary_detail.get("value", "")
    if hasattr(entry, "summary"):
        return entry.summary or ""
    return ""


def parse_rss_feed(url: str, source_name: str = "", timeout: int = 30) -> List[FeedEntry]:
    """
    解析 RSS/Atom Feed，返回标准化的 FeedEntry 列表。

    Args:
        url: RSS Feed URL
        source_name: 情报源名称（用于填充 entry.source_name）
        timeout: 请求超时秒数

    Returns:
        FeedEntry 列表，解析失败时返回空列表
    """
    logger.info("Fetching RSS: %s", url)
    try:
        feed = feedparser.parse(
            url,
            request_headers={"User-Agent": "SecurityIntelAgent/1.0"},
            agent="SecurityIntelAgent/1.0",
        )
    except Exception as e:
        logger.error("feedparser error for %s: %s", url, e)
        return []

    if feed.bozo and feed.bozo_exception:
        logger.warning("Feed %s has bozo error: %s", url, feed.bozo_exception)

    entries = []
    for entry in feed.entries:
        title = getattr(entry, "title", "") or ""
        link = getattr(entry, "link", "") or ""
        if not title or not link:
            continue

        content = _extract_content(entry)
        summary = getattr(entry, "summary", "") or content[:500]
        published_at = _parse_published(entry)

        entries.append(FeedEntry(
            title=title.strip(),
            link=link.strip(),
            content=content,
            summary=summary,
            published_at=published_at,
            source_name=source_name or _extract_domain(url),
        ))

    logger.info("Parsed %d entries from %s", len(entries), url)
    return entries


def _extract_domain(url: str) -> str:
    try:
        return urlparse(url).netloc
    except Exception:
        return url
