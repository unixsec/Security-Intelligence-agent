# ================================================================
# 安全情报分析智能体 — ORM 数据模型
# 版本：v1.0
# 作者：alex (unix_sec@163.com)
# 日期：2026-03-04
# ================================================================

from datetime import datetime

from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Enum, JSON,
    SmallInteger, String, Text, DECIMAL, Date, UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class IntelSource(Base):
    __tablename__ = "intel_sources"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    source_type = Column(
        Enum("rss", "wechat", "website", "search_keyword"), nullable=False
    )
    name = Column(String(200), nullable=False)
    url = Column(String(2000))
    category = Column(String(50), nullable=False, default="general_security")
    language = Column(Enum("zh", "en", "other"), nullable=False, default="zh")
    priority = Column(Enum("high", "medium", "low"), nullable=False, default="medium")
    status = Column(
        Enum("active", "paused", "error"), nullable=False, default="active"
    )
    health_score = Column(SmallInteger, nullable=False, default=100)
    last_success_at = Column(DateTime)
    fail_count = Column(SmallInteger, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow,
                        onupdate=datetime.utcnow)
    created_by = Column(String(100))
    notes = Column(Text)


class SearchKeyword(Base):
    __tablename__ = "search_keywords"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    keyword = Column(String(200), nullable=False)
    category = Column(
        Enum("general_security", "enterprise_it", "automotive",
             "compliance", "supply_chain"),
        nullable=False,
    )
    language = Column(Enum("zh", "en"), nullable=False, default="zh")
    status = Column(Enum("active", "paused"), nullable=False, default="active")
    daily_quota = Column(SmallInteger, nullable=False, default=10)
    last_used_at = Column(DateTime)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow,
                        onupdate=datetime.utcnow)


class RawIntel(Base):
    __tablename__ = "raw_intel"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    source_id = Column(BigInteger)
    source_name = Column(String(200), nullable=False)
    source_url = Column(String(2000))
    title = Column(String(500), nullable=False)
    content = Column(Text)
    summary = Column(Text)
    language = Column(Enum("zh", "en", "other"), nullable=False, default="zh")
    collected_at = Column(DateTime, nullable=False)
    published_at = Column(DateTime)
    content_hash = Column(String(64), nullable=False, unique=True)
    status = Column(
        Enum("pending", "processing", "analyzed", "duplicate", "error"),
        nullable=False,
        default="pending",
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("content_hash", name="uk_content_hash"),
    )


class ScoredIntel(Base):
    __tablename__ = "scored_intel"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    raw_intel_id = Column(BigInteger, nullable=False)
    title = Column(String(500), nullable=False)
    intel_type = Column(
        Enum("vulnerability", "attack", "regulation", "data_breach",
             "opinion", "trend", "technology", "industry"),
        nullable=False,
    )
    severity = Column(Enum("high", "medium", "low"), nullable=False)
    summary_zh = Column(Text, nullable=False)
    score_threat = Column(SmallInteger, nullable=False)
    score_business = Column(SmallInteger, nullable=False)
    score_compliance = Column(SmallInteger, nullable=False)
    score_urgency = Column(SmallInteger, nullable=False)
    score_quality = Column(SmallInteger, nullable=False)
    total_score = Column(DECIMAL(5, 2), nullable=False)
    p_level = Column(Enum("P0", "P1", "P2"), nullable=False, default="P2")
    asset_domain = Column(String(100))
    affected_markets = Column(JSON)
    cve_id = Column(String(50))
    cvss_score = Column(DECIMAL(3, 1))
    poc_status = Column(Enum("none", "public", "in_wild"))
    attack_vector = Column(String(100))
    affected_components = Column(Text)
    impact_analysis = Column(Text)
    recommendations = Column(JSON)
    ai_commentary = Column(Text)
    event_track_id = Column(BigInteger)
    is_pushed = Column(Boolean, nullable=False, default=False)
    push_report_type = Column(String(20))
    scored_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    scoring_model_ver = Column(String(20), nullable=False, default="1.0")


class SystemConfig(Base):
    __tablename__ = "system_configs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    config_key = Column(String(100), nullable=False, unique=True)
    config_value = Column(JSON, nullable=False)
    description = Column(String(500))
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow,
                        onupdate=datetime.utcnow)
    updated_by = Column(String(100))
