# ================================================================
# 安全情报分析智能体 — RSS 采集器主入口（K8s CronJob）
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
from parser import parse_rss_feed

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("rss_collector")


def main():
    logger.info("RSS Collector starting (v1.0)...")

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
                IntelSource.source_type == "rss",
                IntelSource.status == "active",
            )
            .order_by(IntelSource.priority.asc())
            .all()
        )

    logger.info("Found %d active RSS sources.", len(sources))

    total_new = 0
    total_dup = 0

    for source in sources:
        logger.info("Processing source: %s (%s)", source.name, source.url)
        entries = parse_rss_feed(source.url, source_name=source.name)

        source_new = 0
        source_dup = 0

        for entry in entries:
            content_hash = compute_content_hash(entry.title, entry.content)

            with db.session() as session:
                if is_duplicate(session, content_hash):
                    source_dup += 1
                    continue

                language = detect_language(entry.content or entry.title)
                raw = RawIntel(
                    source_id=source.id,
                    source_name=source.name,
                    source_url=entry.link,
                    title=entry.title,
                    content=entry.content,
                    summary=entry.summary,
                    language=language,
                    collected_at=datetime.utcnow(),
                    published_at=entry.published_at,
                    content_hash=content_hash,
                    status="pending",
                )
                try:
                    session.add(raw)
                    session.flush()
                    raw_id = raw.id
                    source_new += 1
                except Exception as e:
                    logger.warning("Insert failed for '%s': %s", entry.title[:50], e)
                    continue

            # 触发 Dify WF-3 语义去重（随后级联触发 WF-2 分析评分）
            result = dify.trigger_dedup(raw_id)
            if not result:
                logger.warning("Dify WF-3 trigger failed for raw_intel_id=%d", raw_id)

        total_new += source_new
        total_dup += source_dup

        # 更新情报源健康状态
        _update_source_health(db, source, success=True)
        logger.info(
            "Source %s: %d new, %d duplicates.", source.name, source_new, source_dup
        )

    logger.info(
        "RSS Collector done. Total new=%d, duplicates=%d.", total_new, total_dup
    )


def _update_source_health(db: DatabaseManager, source: IntelSource, success: bool):
    """更新情报源的健康状态和采集计数。"""
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
                logger.error(
                    "Source %s failed 3 times consecutively, marked as error.",
                    src.name,
                )


if __name__ == "__main__":
    main()
