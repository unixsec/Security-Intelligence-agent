# ================================================================
# 安全情报分析智能体 — 搜索采集器主入口（K8s CronJob）
# 版本：v1.0
# 作者：alex (unix_sec@163.com)
# 日期：2026-03-04
# ================================================================

import logging
import os
import sys
from datetime import datetime

from common.config import load_config
from common.db import DatabaseManager
from common.dedup import compute_content_hash, detect_language, is_duplicate
from common.dify_client import DifyClient
from common.models import RawIntel, SearchKeyword
from search_api import Search360Client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("search_collector")


def main():
    logger.info("Search Collector starting (v1.0)...")

    cfg = load_config()
    db = DatabaseManager(cfg.db)
    dify = DifyClient(cfg.dify)

    search_api_key = os.environ["SEARCH_API_KEY"]
    search_client = Search360Client(api_key=search_api_key)

    if not db.health_check():
        logger.critical("Database unreachable, aborting.")
        sys.exit(1)

    with db.session() as session:
        keywords = (
            session.query(SearchKeyword)
            .filter(SearchKeyword.status == "active")
            .all()
        )

    logger.info("Found %d active search keywords.", len(keywords))

    total_new = 0

    for kw in keywords:
        logger.info("Searching: '%s' (category=%s)", kw.keyword, kw.category)
        results = search_client.search(kw.keyword, num_results=kw.daily_quota)

        kw_new = 0
        for result in results:
            content = result.snippet or result.title
            content_hash = compute_content_hash(result.title, content)

            with db.session() as session:
                if is_duplicate(session, content_hash):
                    continue

                language = detect_language(content)
                raw = RawIntel(
                    source_id=None,
                    source_name=f"360搜索/{kw.keyword}",
                    source_url=result.url,
                    title=result.title,
                    content=content,
                    summary=result.snippet,
                    language=language,
                    collected_at=datetime.utcnow(),
                    published_at=result.published_at,
                    content_hash=content_hash,
                    status="pending",
                )
                try:
                    session.add(raw)
                    session.flush()
                    raw_id = raw.id
                    kw_new += 1
                except Exception as e:
                    logger.warning("Insert failed: %s", e)
                    continue

            dify.trigger_dedup(raw_id)

        # 更新关键词最后使用时间
        with db.session() as session:
            kw_obj = session.get(SearchKeyword, kw.id)
            if kw_obj:
                kw_obj.last_used_at = datetime.utcnow()

        total_new += kw_new
        logger.info("Keyword '%s': %d new intel.", kw.keyword, kw_new)

    logger.info("Search Collector done. Total new=%d.", total_new)


if __name__ == "__main__":
    main()
