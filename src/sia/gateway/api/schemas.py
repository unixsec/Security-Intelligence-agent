"""Pydantic schemas for API request/response validation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


# --- Intelligence ---

class IntelligenceListItem(BaseModel):
    id: int
    title: str
    title_zh: str | None = None
    primary_category: str | None = None
    priority_level: str = "P2"
    total_score: float | None = None
    source_name: str | None = None
    cve_id: str | None = None
    processing_status: str = "raw"
    published_at: datetime
    collected_at: datetime

    model_config = {"from_attributes": True}


class IntelligenceDetail(IntelligenceListItem):
    # Intelligence.tags / mitre_* are stored as JSON and can arrive from the
    # LLM as either a list of strings or an object keyed by subcategory.
    # Keep the schema permissive so both serializations round-trip.
    content: str
    content_zh: str | None = None
    summary: str | None = None
    summary_zh: str | None = None
    secondary_category: str | None = None
    tags: list[str] | dict[str, Any] | None = None
    tlp_level: str = "GREEN"
    score_relevance: float | None = None
    score_severity: float | None = None
    score_timeliness: float | None = None
    score_actionability: float | None = None
    score_quality: float | None = None
    llm_comment: str | None = None
    llm_impact: str | None = None
    llm_action: str | None = None
    llm_model_used: str | None = None
    mitre_tactics: list[str] | dict[str, Any] | None = None
    mitre_techniques: list[str] | dict[str, Any] | None = None
    cvss_score: float | None = None
    epss_score: float | None = None
    is_kev: bool = False
    analyzed_at: datetime | None = None


class IntelligenceQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    priority: str | None = None
    category: str | None = None
    status: str | None = None
    keyword: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    sort_by: str = "collected_at"
    sort_order: str = "desc"


# --- Sources ---

class SourceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    name_en: str | None = None
    source_type: str = "rss"
    url: str
    fetch_interval: int = Field(default=240, ge=10, le=10080)
    language: str = "en"
    default_category: str | None = None
    reliability: str = "professional"

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Prevent SSRF: only allow http/https schemes, block internal networks."""
        from urllib.parse import urlparse
        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("Only http/https URLs are allowed")
        hostname = parsed.hostname or ""
        # Block internal/private networks
        blocked = ("localhost", "127.0.0.1", "0.0.0.0", "169.254.", "[::1]")
        if any(hostname.startswith(b) for b in blocked):
            raise ValueError("Internal network URLs are not allowed")
        if hostname.endswith(".internal") or hostname.endswith(".local"):
            raise ValueError("Internal network URLs are not allowed")
        import ipaddress
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                raise ValueError("Private/loopback IP addresses are not allowed")
        except ValueError:
            pass  # Not an IP, that's fine (it's a hostname)
        return v

    @field_validator("source_type")
    @classmethod
    def validate_source_type(cls, v: str) -> str:
        allowed = {"rss", "api", "web_crawl", "manual"}
        if v not in allowed:
            raise ValueError(f"source_type must be one of {allowed}")
        return v


class SourceResponse(BaseModel):
    id: int
    name: str
    source_type: str
    url: str
    status: str
    last_fetched_at: datetime | None = None
    error_count: int = 0

    model_config = {"from_attributes": True}


# --- Reports ---

class ReportListItem(BaseModel):
    id: int
    title: str
    report_type: str
    report_date: Any
    status: str
    p0_count: int = 0
    p1_count: int = 0
    generated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ReportGenerateRequest(BaseModel):
    report_type: str = "daily"
    audience: str = "executive"
    period_start: str | None = None
    period_end: str | None = None

    @field_validator("report_type")
    @classmethod
    def validate_report_type(cls, v: str) -> str:
        allowed = {"daily", "weekly", "monthly", "quarterly", "emergency"}
        if v not in allowed:
            raise ValueError(f"report_type must be one of {allowed}")
        return v


# --- Dashboard ---

class DashboardStats(BaseModel):
    total_intel: int = 0
    today_collected: int = 0
    p0_active: int = 0
    p1_active: int = 0
    active_events: int = 0
    active_sources: int = 0
    analysis_queue_size: int = 0


class ProviderStatus(BaseModel):
    name: str
    state: str
    failure_count: int = 0
    provider_type: str = ""


# --- System ---

class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str = ""
    uptime_seconds: float = 0
    database: str = "unknown"
    redis: str = "unknown"
    llm_providers: list[ProviderStatus] = []


class PaginatedResponse(BaseModel):
    items: list[Any] = []
    total: int = 0
    page: int = 1
    page_size: int = 20
    pages: int = 0
