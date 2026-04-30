"""Group + group membership models (v0.4-3 resource-level RBAC)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from sia.common.database import Base


class Group(Base):
    """A team / organisational unit. Holds extra permissions + ownership tag."""
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))
    # Each entry is "resource:action", e.g. "reports:generate". Resolved by
    # ``permissions.has_permission`` at request time.
    extra_permissions: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    # Ownership tag attached to resources (sources, reports) when a row
    # belongs to this team. Filtering happens at the query layer (v0.4).
    owns_tag: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class UserGroup(Base):
    """Many-to-many: users ↔ groups."""
    __tablename__ = "user_groups"
    __table_args__ = (UniqueConstraint("user_id", "group_id", name="uq_user_group"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    group_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("groups.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
