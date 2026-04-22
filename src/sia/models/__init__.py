"""SQLAlchemy ORM models for SIA.

Importing this package registers every model with Base.metadata. init_db()
relies on that registration, so new model modules MUST be imported here.
"""

from sia.models.intelligence import Intelligence, SecurityEvent
from sia.models.source import IntelSource, SearchKeyword
from sia.models.report import Report, ReportIntelMap, PushLog
from sia.models.system import (
    AuditLog,
    Feedback,
    Outbox,
    Subscriber,
    PushGroup,
    EnterpriseAsset,
    SupplyChainVendor,
    ScoringConfig,
    ScoringOverride,
    IocIndicator,
    MitreAttack,
    WorkflowRun,
    LLMCallLog,
    HolidayCalendar,
)
from sia.models.user import RefreshToken, User

__all__ = [
    "Intelligence",
    "SecurityEvent",
    "IntelSource",
    "SearchKeyword",
    "Report",
    "ReportIntelMap",
    "PushLog",
    "AuditLog",
    "Feedback",
    "Outbox",
    "Subscriber",
    "PushGroup",
    "EnterpriseAsset",
    "SupplyChainVendor",
    "ScoringConfig",
    "ScoringOverride",
    "IocIndicator",
    "MitreAttack",
    "WorkflowRun",
    "LLMCallLog",
    "HolidayCalendar",
    "User",
    "RefreshToken",
]
