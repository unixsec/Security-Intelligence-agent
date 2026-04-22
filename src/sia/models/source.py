"""Intel source and search keyword models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from sia.common.database import Base


class IntelSource(Base):
    """Intelligence source configuration."""

    __tablename__ = "intel_sources"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(200))

    source_type: Mapped[str] = mapped_column(
        Enum("rss", "web_crawl", "api", "wechat", "tor", "manual", name="source_type_enum"),
        nullable=False,
    )
    url: Mapped[str] = mapped_column(String(2000), nullable=False)
    backup_url: Mapped[str | None] = mapped_column(String(2000))

    # Collection config
    fetch_interval: Mapped[int] = mapped_column(Integer, default=240)
    fetch_timeout: Mapped[int] = mapped_column(Integer, default=30)
    max_items: Mapped[int] = mapped_column(Integer, default=50)
    use_proxy: Mapped[bool] = mapped_column(Boolean, default=True)
    custom_headers: Mapped[dict | None] = mapped_column(JSON)
    css_selectors: Mapped[dict | None] = mapped_column(JSON)
    api_config: Mapped[dict | None] = mapped_column(JSON)

    # Keywords
    search_keywords: Mapped[dict | None] = mapped_column(JSON)

    # Quality
    language: Mapped[str] = mapped_column(
        Enum("zh", "en", "both", name="source_lang_enum"), default="en"
    )
    default_category: Mapped[str | None] = mapped_column(String(50))
    reliability: Mapped[str] = mapped_column(
        Enum("official", "authority", "professional", "general", "unverified",
             name="reliability_enum"),
        default="professional",
    )

    # Status
    status: Mapped[str] = mapped_column(
        Enum("active", "paused", "error", "deprecated", name="source_status_enum"),
        default="active",
        index=True,
    )
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Legal approval (for Tor sources)
    legal_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    legal_approved_by: Mapped[str | None] = mapped_column(String(100))
    legal_approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    legal_expires_at: Mapped[datetime | None] = mapped_column(DateTime)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, onupdate=datetime.now)


class SearchKeyword(Base):
    """Search keywords for intel collection and matching."""

    __tablename__ = "search_keywords"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    keyword: Mapped[str] = mapped_column(String(200), nullable=False)
    keyword_en: Mapped[str | None] = mapped_column(String(200))
    category: Mapped[str | None] = mapped_column(String(50), index=True)
    scope: Mapped[str] = mapped_column(
        Enum("title", "content", "both", name="keyword_scope_enum"), default="both"
    )
    is_regex: Mapped[bool] = mapped_column(Boolean, default=False)
    priority_boost: Mapped[float] = mapped_column(default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
