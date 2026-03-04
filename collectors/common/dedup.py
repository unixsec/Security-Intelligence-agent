# ================================================================
# 安全情报分析智能体 — 内容哈希粗去重模块
# 版本：v1.0
# 作者：alex (unix_sec@163.com)
# 日期：2026-03-04
# ================================================================

import hashlib
import logging

from sqlalchemy.orm import Session

from .models import RawIntel

logger = logging.getLogger(__name__)


def compute_content_hash(title: str, content: str) -> str:
    """
    计算情报内容哈希，用于第一阶段粗去重。
    哈希输入：标题 + 内容前 500 字符（稳定内容特征）。
    """
    payload = (title + content[:500]).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def is_duplicate(session: Session, content_hash: str) -> bool:
    """
    检查 raw_intel 表中是否已存在相同 content_hash 的记录。
    第一阶段粗去重（精确哈希匹配），第二阶段由 Milvus 语义去重处理。
    """
    exists = (
        session.query(RawIntel)
        .filter(RawIntel.content_hash == content_hash)
        .first()
    )
    if exists:
        logger.debug("Duplicate detected (hash=%s), skipping.", content_hash[:16])
    return exists is not None


def detect_language(text: str) -> str:
    """
    简单语言检测：统计中文字符比例。
    中文字符比例 > 20% 则判定为中文，否则为英文。
    """
    if not text:
        return "zh"
    chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    ratio = chinese_chars / max(len(text), 1)
    if ratio > 0.20:
        return "zh"
    return "en"
