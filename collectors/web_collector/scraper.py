# ================================================================
# 安全情报分析智能体 — 网页内容抓取器
# 版本：v1.0
# 作者：alex (unix_sec@163.com)
# 日期：2026-03-04
# ================================================================

import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# 静态抓取优先，动态页面（JavaScript 渲染）使用 Playwright
_REQUESTS_TIMEOUT = 30
_USER_AGENT = (
    "Mozilla/5.0 (compatible; SecurityIntelAgent/1.0; "
    "+https://github.com/security-intel-agent)"
)


@dataclass
class ScrapedPage:
    url: str
    title: str
    content: str
    summary: str
    published_at: Optional[datetime]


def scrape_url(url: str, use_playwright: bool = False) -> Optional[ScrapedPage]:
    """
    抓取指定 URL 的网页内容。
    优先使用 requests + BeautifulSoup（轻量快速），
    若页面需要 JS 渲染，则使用 Playwright。
    """
    if use_playwright:
        return _scrape_with_playwright(url)
    return _scrape_with_requests(url)


def _scrape_with_requests(url: str) -> Optional[ScrapedPage]:
    """使用 requests + BeautifulSoup 抓取静态页面。"""
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": _USER_AGENT},
            timeout=_REQUESTS_TIMEOUT,
            allow_redirects=True,
        )
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
        return _parse_html(url, resp.text)
    except requests.RequestException as e:
        logger.warning("requests scrape failed for %s: %s", url, e)
        return None


def _scrape_with_playwright(url: str) -> Optional[ScrapedPage]:
    """使用 Playwright 抓取需要 JS 渲染的动态页面。"""
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent=_USER_AGENT,
                extra_http_headers={"Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"},
            )
            page.goto(url, timeout=60000, wait_until="networkidle")
            time.sleep(2)
            html = page.content()
            browser.close()
        return _parse_html(url, html)
    except Exception as e:
        logger.warning("playwright scrape failed for %s: %s", url, e)
        return None


def _parse_html(url: str, html: str) -> Optional[ScrapedPage]:
    """解析 HTML，提取标题、正文和发布时间。"""
    soup = BeautifulSoup(html, "html.parser")

    # 提取标题
    title = ""
    if soup.title:
        title = soup.title.string or ""
    if not title:
        h1 = soup.find("h1")
        title = h1.get_text(strip=True) if h1 else ""

    # 移除噪声标签
    for tag in soup(["script", "style", "nav", "footer", "header",
                     "aside", "iframe", "noscript"]):
        tag.decompose()

    # 提取正文（优先 article / main，否则 body）
    content_node = (
        soup.find("article")
        or soup.find("main")
        or soup.find(id=re.compile(r"(content|article|post)", re.I))
        or soup.body
    )
    content = content_node.get_text(separator="\n", strip=True) if content_node else ""

    # 简单摘要（前 300 字符）
    summary = content[:300].replace("\n", " ")

    # 尝试提取发布时间
    published_at = _extract_date(soup)

    if not title and not content:
        logger.warning("Empty content extracted from %s", url)
        return None

    return ScrapedPage(
        url=url,
        title=title.strip(),
        content=content,
        summary=summary,
        published_at=published_at,
    )


def _extract_date(soup: BeautifulSoup) -> Optional[datetime]:
    """从 HTML 元数据或常见时间标签中提取发布日期。"""
    # meta og:published_time
    meta = soup.find("meta", attrs={"property": "article:published_time"})
    if meta and meta.get("content"):
        return _parse_date_str(meta["content"])

    # <time> 标签
    time_tag = soup.find("time")
    if time_tag:
        dt_str = time_tag.get("datetime") or time_tag.get_text(strip=True)
        parsed = _parse_date_str(dt_str)
        if parsed:
            return parsed

    return None


def _parse_date_str(s: str) -> Optional[datetime]:
    formats = [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(s[:25], fmt)
            return dt.replace(tzinfo=None)
        except (ValueError, TypeError):
            continue
    return None
