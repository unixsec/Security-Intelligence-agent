"""API key model with role + path scopes (SEC-2).

A request authenticated via ``X-API-Key`` is granted the role and the path
scopes recorded against the matching key. The key itself is stored as a
SHA-256 hex digest (``key_hash``); the plaintext is shown to the operator
exactly once at creation time.

The legacy single-key ``SIA_API_KEY`` env var continues to work as a
fallback when no DB key matches; that path grants ``admin`` + ``*`` so
existing deployments do not break.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from sia.common.database import Base


class APIKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    # SHA-256 hex digest of the plaintext key (64 chars).
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    role: Mapped[str] = mapped_column(
        Enum("admin", "analyst", "viewer", name="api_key_role"),
        nullable=False,
        default="viewer",
    )
    # JSON list of allowed path prefixes. ``["*"]`` means any path.
    scopes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    disabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)

    def __repr__(self) -> str:
        return f"<APIKey name={self.name} role={self.role}>"
