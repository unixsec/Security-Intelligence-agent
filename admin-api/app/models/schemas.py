# ================================================================
# 安全情报分析智能体 — Pydantic 请求/响应 Schema
# 版本：v1.0
# 作者：alex (unix_sec@163.com)
# 日期：2026-03-04
# ================================================================

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---- 通用响应 ----

class PagedResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[Any]


class SuccessResponse(BaseModel):
    success: bool = True
    message: str = "OK"


# ---- 情报源 ----

class IntelSourceCreate(BaseModel):
    source_type: str = Field(..., pattern="^(rss|wechat|website|search_keyword)$")
    name: str = Field(..., min_length=1, max_length=200)
    url: Optional[str] = None
    category: str = "general_security"
    language: str = Field("zh", pattern="^(zh|en|other)$")
    priority: str = Field("medium", pattern="^(high|medium|low)$")
    notes: Optional[str] = None


class IntelSourceUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    category: Optional[str] = None
    language: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class IntelSourceResponse(BaseModel):
    id: int
    source_type: str
    name: str
    url: Optional[str]
    category: str
    language: str
    priority: str
    status: str
    health_score: int
    last_success_at: Optional[datetime]
    fail_count: int
    created_at: datetime
    updated_at: datetime
    notes: Optional[str]

    class Config:
        from_attributes = True


# ---- 搜索关键词 ----

class KeywordCreate(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=200)
    category: str
    language: str = Field("zh", pattern="^(zh|en)$")
    daily_quota: int = Field(10, ge=1, le=50)


class KeywordUpdate(BaseModel):
    keyword: Optional[str] = None
    category: Optional[str] = None
    language: Optional[str] = None
    status: Optional[str] = None
    daily_quota: Optional[int] = None


class KeywordResponse(BaseModel):
    id: int
    keyword: str
    category: str
    language: str
    status: str
    daily_quota: int
    last_used_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


# ---- 原始情报 ----

class RawIntelResponse(BaseModel):
    id: int
    source_name: str
    source_url: Optional[str]
    title: str
    summary: Optional[str]
    language: str
    collected_at: datetime
    published_at: Optional[datetime]
    status: str

    class Config:
        from_attributes = True


# ---- 已评分情报 ----

class ScoredIntelResponse(BaseModel):
    id: int
    raw_intel_id: int
    title: str
    intel_type: str
    severity: str
    summary_zh: str
    score_threat: int
    score_business: int
    score_compliance: int
    score_urgency: int
    score_quality: int
    total_score: float
    p_level: str
    asset_domain: Optional[str]
    affected_markets: Optional[List[str]]
    cve_id: Optional[str]
    cvss_score: Optional[float]
    poc_status: Optional[str]
    impact_analysis: Optional[str]
    recommendations: Optional[List[str]]
    ai_commentary: Optional[str]
    is_pushed: bool
    scored_at: datetime

    class Config:
        from_attributes = True


# ---- 报告 ----

class ReportResponse(BaseModel):
    id: int
    report_type: str
    report_code: str
    report_version: str
    period_start: datetime
    period_end: datetime
    status: str
    generated_at: Optional[datetime]
    pushed_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


# ---- 系统配置 ----

class ConfigUpdate(BaseModel):
    config_value: Dict[str, Any]


class ConfigResponse(BaseModel):
    config_key: str
    config_value: Dict[str, Any]
    description: Optional[str]
    updated_at: datetime
    updated_by: Optional[str]

    class Config:
        from_attributes = True


# ---- 仪表盘 ----

class DashboardStats(BaseModel):
    total_sources: int
    active_sources: int
    error_sources: int
    today_raw_intel: int
    today_scored_intel: int
    today_p0_alerts: int
    today_p1_alerts: int
    today_reports: int
    last_updated: datetime


class HealthStatus(BaseModel):
    status: str  # healthy / degraded / critical
    database: bool
    dify_api: bool
    active_sources_ratio: float
    details: Dict[str, Any]
