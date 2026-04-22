"""Report and push log models."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from sia.common.database import Base


class Report(Base):
    """Generated reports (daily, weekly, monthly, etc.)."""

    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    report_type: Mapped[str] = mapped_column(
        Enum("daily", "weekly", "monthly", "quarterly", "semi_annual", "annual", "emergency",
             name="report_type_enum"),
        nullable=False,
    )
    report_version: Mapped[str] = mapped_column(
        Enum("executive", "operational", name="report_version_enum"), nullable=False
    )
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    sequence_no: Mapped[int | None] = mapped_column(Integer)

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    content_html: Mapped[str | None] = mapped_column(Text)
    content_json: Mapped[dict | None] = mapped_column(JSON)

    # Threat level
    threat_level: Mapped[str | None] = mapped_column(
        Enum("critical", "high", "medium", "low", name="threat_level_enum")
    )
    situation_summary: Mapped[str | None] = mapped_column(Text)
    ai_insight: Mapped[str | None] = mapped_column(Text)

    # Stats
    intel_total: Mapped[int | None] = mapped_column(Integer)
    intel_selected: Mapped[int | None] = mapped_column(Integer)
    p0_count: Mapped[int] = mapped_column(Integer, default=0)
    p1_count: Mapped[int] = mapped_column(Integer, default=0)

    # Distribution
    tlp_level: Mapped[str] = mapped_column(
        Enum("RED", "AMBER", "GREEN", "CLEAR", name="report_tlp_enum"), default="GREEN"
    )

    # Approval
    approval_status: Mapped[str] = mapped_column(
        Enum("pending", "approved", "rejected", "auto_approved", name="approval_enum"),
        default="pending",
    )
    approved_by: Mapped[str | None] = mapped_column(String(100))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Files
    pdf_path: Mapped[str | None] = mapped_column(String(500))

    # Status
    status: Mapped[str] = mapped_column(
        Enum("generating", "generated", "pushing", "pushed", "failed", name="report_status_enum"),
        default="generating",
        index=True,
    )
    generated_at: Mapped[datetime | None] = mapped_column(DateTime)
    pushed_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Period
    period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ReportIntelMap(Base):
    """Many-to-many mapping between reports and intelligence items."""

    __tablename__ = "report_intel_map"

    report_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("reports.id"), primary_key=True
    )
    intel_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("intelligence.id"), primary_key=True
    )
    display_order: Mapped[int] = mapped_column(Integer, default=0)


class PushLog(Base):
    """Push notification delivery log."""

    __tablename__ = "push_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    report_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    intel_id: Mapped[int | None] = mapped_column(BigInteger)
    push_type: Mapped[str] = mapped_column(
        Enum("report", "emergency", name="push_type_enum"), nullable=False
    )

    channel: Mapped[str] = mapped_column(
        Enum("wechat_work", "feishu", "email", "sms", name="channel_enum"), nullable=False
    )
    target_type: Mapped[str] = mapped_column(
        Enum("individual", "group", name="target_type_enum"), nullable=False
    )
    target_id: Mapped[str] = mapped_column(String(200), nullable=False)

    status: Mapped[str] = mapped_column(
        Enum("pending", "sent", "delivered", "failed", name="push_status_enum"),
        default="pending",
        index=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime)
