# ================================================================
# 安全情报分析智能体 — 网页采集器主入口（K8s CronJob）
# 版本：v1.0
# 作者：alex (unix_sec@163.com)
# 日期：2026-03-04
# ================================================================

import logging
import sys
from datetime import datetime

from common.config import load_config
from common.db import DatabaseManager
from common.dedup import compute_content_hash, detect_language, is_duplicate
from common.dify_client import DifyClient
from common.models import IntelSource, RawIntel
from scraper import scrape_url

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("web_collector")


def main():
    logger.info("Web Collector starting (v1.0)...")

    cfg = load_config()
    db = DatabaseManager(cfg.db)
    dify = DifyClient(cfg.dify)

    if not db.health_check():
        logger.critical("Database unreachable, aborting.")
        sys.exit(1)

    with db.session() as session:
        sources = (
            session.query(IntelSource)
            .filter(
                IntelSource.source_type == "website",
                IntelSource.status == "active",
            )
            .all()
        )

    logger.info("Found %d active website sources.", len(sources))

    for source in sources:
        logger.info("Scraping: %s (%s)", source.name, source.url)
        use_playwright = (source.notes or "").lower().find("playwright") >= 0
        page = scrape_url(source.url, use_playwright=use_playwright)

        if not page or not page.title:
            logger.warning("Failed to scrape %s, updating fail_count.", source.name)
            _update_source_health(db, source, success=False)
            continue

        content_hash = compute_content_hash(page.title, page.content)

        with db.session() as session:
            if is_duplicate(session, content_hash):
                logger.debug("Duplicate: %s", page.title[:60])
                _update_source_health(db, source, success=True)
                continue

            language = detect_language(page.content or page.title)
            raw = RawIntel(
                source_id=source.id,
                source_name=source.name,
                source_url=page.url,
                title=page.title,
                content=page.content,
                summary=page.summary,
                language=language,
                collected_at=datetime.utcnow(),
                published_at=page.published_at,
                content_hash=content_hash,
                status="pending",
            )
            try:
                session.add(raw)
                session.flush()
                raw_id = raw.id
            except Exception as e:
                logger.warning("Insert failed for '%s': %s", page.title[:50], e)
                continue

        dify.trigger_dedup(raw_id)
        _update_source_health(db, source, success=True)
        logger.info("New intel from %s: %s", source.name, page.title[:60])

    logger.info("Web Collector done.")


def _update_source_health(db: DatabaseManager, source: IntelSource, success: bool):
    with db.session() as session:
        src = session.get(IntelSource, source.id)
        if not src:
            return
        if success:
            src.last_success_at = datetime.utcnow()
            src.fail_count = 0
            src.health_score = 100
            src.status = "active"
        else:
            src.fail_count = (src.fail_count or 0) + 1
            src.health_score = max(0, 100 - src.fail_count * 30)
            if src.fail_count >= 3:
                src.status = "error"
                src.health_score = 0


if __name__ == "__main__":
    main()
