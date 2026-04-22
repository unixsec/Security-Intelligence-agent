"""System models: audit, feedback, outbox, subscribers, assets, etc."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from sia.common.database import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    current_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(50))
    entity_id: Mapped[str | None] = mapped_column(String(50))
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    actor: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    actor_ip: Mapped[str | None] = mapped_column(String(45))
    details: Mapped[dict | None] = mapped_column(JSON)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    intel_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    report_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    subscriber_id: Mapped[int] = mapped_column(Integer, nullable=False)
    feedback_type: Mapped[str] = mapped_column(
        Enum("useful", "useless", "rating", "comment", name="feedback_type_enum")
    )
    rating: Mapped[int | None] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Outbox(Base):
    __tablename__ = "outbox"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    action: Mapped[str] = mapped_column(
        Enum("create", "update", "delete", name="outbox_action_enum"), nullable=False
    )
    payload: Mapped[dict | None] = mapped_column(JSON)
    targets: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(
        Enum("pending", "processing", "completed", "failed", name="outbox_status_enum"),
        default="pending",
        index=True,
    )
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime)


class Subscriber(Base):
    __tablename__ = "subscribers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str | None] = mapped_column(String(100), index=True)
    department: Mapped[str | None] = mapped_column(String(100))
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Shanghai")

    wechat_work_id: Mapped[str | None] = mapped_column(String(200))
    feishu_id: Mapped[str | None] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(20))

    subscribe_level: Mapped[str] = mapped_column(
        Enum("all", "p0_p1_only", "daily", "weekly", "monthly", name="sub_level_enum"),
        default="all",
    )
    subscribe_version: Mapped[str] = mapped_column(
        Enum("executive", "operational", "both", name="sub_version_enum"),
        default="executive",
    )
    preferred_channel: Mapped[str] = mapped_column(
        Enum("wechat_work", "feishu", "email", name="pref_channel_enum"),
        default="wechat_work",
    )
    max_tlp_level: Mapped[str] = mapped_column(
        Enum("RED", "AMBER", "GREEN", "CLEAR", name="sub_tlp_enum"), default="GREEN"
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class PushGroup(Base):
    __tablename__ = "push_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    trigger_levels: Mapped[dict] = mapped_column(JSON, nullable=False)
    report_types: Mapped[dict] = mapped_column(JSON, nullable=False)
    channels: Mapped[dict] = mapped_column(JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class EnterpriseAsset(Base):
    __tablename__ = "enterprise_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_type: Mapped[str] = mapped_column(String(50), nullable=False)
    vendor: Mapped[str] = mapped_column(String(200), nullable=False)
    product: Mapped[str] = mapped_column(String(200), nullable=False)
    version_range: Mapped[str | None] = mapped_column(String(100))
    cpe_id: Mapped[str | None] = mapped_column(String(500), index=True)
    department: Mapped[str | None] = mapped_column(String(200))
    criticality: Mapped[str] = mapped_column(String(20), default="medium")
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, onupdate=datetime.now)


class SupplyChainVendor(Base):
    __tablename__ = "supply_chain_vendors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vendor_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    vendor_name_en: Mapped[str | None] = mapped_column(String(200))
    vendor_aliases: Mapped[dict | None] = mapped_column(JSON)
    tier: Mapped[str] = mapped_column(String(20), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    products_used: Mapped[dict | None] = mapped_column(JSON)
    risk_level: Mapped[str] = mapped_column(String(20), default="medium")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, onupdate=datetime.now)


class ScoringConfig(Base):
    __tablename__ = "scoring_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dimension: Mapped[str] = mapped_column(String(50), nullable=False)
    weight: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False)
    scoring_rules: Mapped[dict] = mapped_column(JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_by: Mapped[str | None] = mapped_column(String(100))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, onupdate=datetime.now)


class ScoringOverride(Base):
    __tablename__ = "scoring_overrides"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_name: Mapped[str] = mapped_column(String(100), nullable=False)
    condition_type: Mapped[str] = mapped_column(String(50), nullable=False)
    condition_value: Mapped[dict] = mapped_column(JSON, nullable=False)
    override_level: Mapped[str] = mapped_column(String(5), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class IocIndicator(Base):
    __tablename__ = "ioc_indicators"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    intel_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    ioc_type: Mapped[str] = mapped_column(String(20), nullable=False)
    ioc_value: Mapped[str] = mapped_column(String(2000), nullable=False)
    context: Mapped[str | None] = mapped_column(String(500))
    confidence: Mapped[str] = mapped_column(String(10), default="medium")
    is_whitelisted: Mapped[bool] = mapped_column(Boolean, default=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class MitreAttack(Base):
    __tablename__ = "mitre_attack"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_zh: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    description_zh: Mapped[str | None] = mapped_column(Text)
    platforms: Mapped[dict | None] = mapped_column(JSON)
    data_sources: Mapped[dict | None] = mapped_column(JSON)
    url: Mapped[str | None] = mapped_column(String(500))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime)


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    workflow_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    trigger_type: Mapped[str] = mapped_column(String(20), nullable=False)
    trigger_detail: Mapped[str | None] = mapped_column(String(500))
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    duration_ms: Mapped[int | None] = mapped_column(BigInteger)
    steps_total: Mapped[int | None] = mapped_column(Integer)
    steps_completed: Mapped[int | None] = mapped_column(Integer)
    steps_failed: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    context_json: Mapped[dict | None] = mapped_column(JSON)
    trace_id: Mapped[str | None] = mapped_column(String(64))


class LLMCallLog(Base):
    __tablename__ = "llm_call_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    model_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    provider_type: Mapped[str] = mapped_column(String(30), nullable=False)
    prompt_template: Mapped[str | None] = mapped_column(String(100))
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    cost_usd: Mapped[float] = mapped_column(Numeric(8, 6), default=0)
    workflow_run_id: Mapped[str | None] = mapped_column(String(50), index=True)
    intel_id: Mapped[int | None] = mapped_column(BigInteger)
    trace_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)


class HolidayCalendar(Base):
    __tablename__ = "holiday_calendar"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    calendar_region: Mapped[str] = mapped_column(String(10), nullable=False)
    holiday_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    holiday_name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_workday: Mapped[bool] = mapped_column(Boolean, default=False)
