"""Intelligence and SecurityEvent ORM models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Index,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from sia.common.database import Base


class Intelligence(Base):
    """Core intelligence table — stores all collected and analyzed intel."""

    __tablename__ = "intelligence"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Basic info
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    title_zh: Mapped[str | None] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_zh: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    summary_zh: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str] = mapped_column(String(2000), nullable=False)
    author: Mapped[str | None] = mapped_column(String(200))
    language: Mapped[str] = mapped_column(
        Enum("zh", "en", "other", name="lang_enum"), default="en"
    )

    # Source
    source_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    source_name: Mapped[str | None] = mapped_column(String(200))

    # Classification
    primary_category: Mapped[str | None] = mapped_column(String(50))
    secondary_category: Mapped[str | None] = mapped_column(String(50))
    tags: Mapped[dict | None] = mapped_column(JSON)

    # Scoring
    score_relevance: Mapped[float | None] = mapped_column(Numeric(3, 1))
    score_severity: Mapped[float | None] = mapped_column(Numeric(3, 1))
    score_timeliness: Mapped[float | None] = mapped_column(Numeric(3, 1))
    score_actionability: Mapped[float | None] = mapped_column(Numeric(3, 1))
    score_quality: Mapped[float | None] = mapped_column(Numeric(3, 1))
    total_score: Mapped[float | None] = mapped_column(Numeric(4, 2))
    priority_level: Mapped[str] = mapped_column(
        Enum("P0", "P1", "P2", "P3", name="priority_enum"), default="P2"
    )

    # TLP
    tlp_level: Mapped[str] = mapped_column(
        Enum("RED", "AMBER", "GREEN", "CLEAR", name="tlp_enum"), default="GREEN"
    )

    # LLM analysis
    llm_comment: Mapped[str | None] = mapped_column(Text)
    llm_impact: Mapped[str | None] = mapped_column(Text)
    llm_action: Mapped[str | None] = mapped_column(Text)
    llm_model_used: Mapped[str | None] = mapped_column(String(50))

    # ATT&CK
    mitre_tactics: Mapped[dict | None] = mapped_column(JSON)
    mitre_techniques: Mapped[dict | None] = mapped_column(JSON)

    # Event tracking
    event_id: Mapped[str | None] = mapped_column(String(50), index=True)

    # Vulnerability
    cve_id: Mapped[str | None] = mapped_column(String(20), index=True)
    cvss_score: Mapped[float | None] = mapped_column(Numeric(3, 1))
    epss_score: Mapped[float | None] = mapped_column(Numeric(5, 4))
    is_kev: Mapped[bool] = mapped_column(Boolean, default=False)
    affected_products: Mapped[dict | None] = mapped_column(JSON)

    # Processing
    processing_status: Mapped[str] = mapped_column(
        Enum("raw", "preprocessed", "analyzed", "published", "archived", name="proc_enum"),
        default="raw",
        index=True,
    )
    fingerprint: Mapped[str | None] = mapped_column(String(64), unique=True)

    # Vector
    vector_id: Mapped[int | None] = mapped_column(BigInteger)

    # Tracing
    trace_id: Mapped[str | None] = mapped_column(String(64))

    # Timestamps
    published_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    collected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime)

    __table_args__ = (
        Index("idx_priority", "priority_level"),
        Index("idx_category", "primary_category", "secondary_category"),
        Index("idx_published", "published_at"),
        Index("idx_collected", "collected_at"),
        Index("idx_total_score", total_score.desc()),
    )


class SecurityEvent(Base):
    """Security event timeline tracking."""

    __tablename__ = "security_events"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    title_zh: Mapped[str | None] = mapped_column(String(500))
    summary: Mapped[str | None] = mapped_column(Text)

    status: Mapped[str] = mapped_column(
        Enum("developing", "cooling_down", "resolved", "archived", name="event_status_enum"),
        default="developing",
        index=True,
    )
    heat_score: Mapped[int] = mapped_column(default=50)

    first_seen: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_updated: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    timeline: Mapped[dict | None] = mapped_column(JSON)
    affected_entities: Mapped[dict | None] = mapped_column(JSON)
    mitre_techniques: Mapped[dict | None] = mapped_column(JSON)
    related_intel_count: Mapped[int] = mapped_column(default=1)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
