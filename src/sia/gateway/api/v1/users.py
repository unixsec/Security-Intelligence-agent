"""User management API endpoints — admin only."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from sia.auth.password import hash_password, validate_password_policy
from sia.auth.rbac import CurrentUser, require_role
from sia.common.database import get_db
from sia.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/users",
    tags=["users"],
    dependencies=[Depends(require_role("admin"))],
)


# ─── Schemas ─────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str = Field(..., min_length=2, max_length=100)
    email: str = Field(..., max_length=255)
    display_name: str = Field("", max_length=200)
    password: str = Field(..., min_length=8)
    role: str = "viewer"

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in ("admin", "analyst", "viewer"):
            raise ValueError("role must be admin, analyst, or viewer")
        return v


class UserUpdate(BaseModel):
    display_name: str | None = None
    email: str | None = None
    role: str | None = None
    status: str | None = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str | None) -> str | None:
        if v is not None and v not in ("admin", "analyst", "viewer"):
            raise ValueError("role must be admin, analyst, or viewer")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is not None and v not in ("active", "disabled"):
            raise ValueError("status must be active or disabled")
        return v


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=8)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    display_name: str
    role: str
    status: str
    auth_provider: str
    last_login_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── List users ──────────────────────────────────────────────────────────────

@router.get("", response_model=list[UserResponse])
async def list_users(
    role: str | None = None,
    status: str | None = None,
    keyword: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List all users (admin only)."""
    query = select(User).order_by(User.created_at.desc())
    if role:
        query = query.where(User.role == role)
    if status:
        query = query.where(User.status == status)
    if keyword:
        safe_kw = keyword.replace("%", r"\%").replace("_", r"\_")
        query = query.where(
            User.username.ilike(f"%{safe_kw}%", escape="\\")
            | User.display_name.ilike(f"%{safe_kw}%", escape="\\")
            | User.email.ilike(f"%{safe_kw}%", escape="\\")
        )
    result = await db.execute(query)
    return [UserResponse.model_validate(u) for u in result.scalars().all()]


# ─── Create user ─────────────────────────────────────────────────────────────

@router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    body: UserCreate,
    admin: CurrentUser = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Create a local user (admin only)."""
    # Check uniqueness
    existing = await db.execute(
        select(User.id).where(
            (User.username == body.username) | (User.email == body.email)
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Username or email already exists")

    # Validate password policy
    errors = validate_password_policy(body.password)
    if errors:
        raise HTTPException(status_code=422, detail="; ".join(errors))

    user = User(
        username=body.username,
        email=body.email,
        display_name=body.display_name or body.username,
        hashed_password=hash_password(body.password),
        role=body.role,
        auth_provider="local",
        status="active",
        password_changed_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.flush()

    logger.info("User created: %s role=%s by=%s", user.username, user.role, admin.username)
    return UserResponse.model_validate(user)


# ─── Get user ────────────────────────────────────────────────────────────────

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)):
    """Get user by ID (admin only)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse.model_validate(user)


# ─── Update user ─────────────────────────────────────────────────────────────

@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    body: UserUpdate,
    admin: CurrentUser = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Update user attributes (admin only)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if body.display_name is not None:
        user.display_name = body.display_name
    if body.email is not None:
        user.email = body.email
    if body.role is not None:
        user.role = body.role
    if body.status is not None:
        user.status = body.status
        if body.status == "active":
            user.failed_login_count = 0
            user.locked_until = None

    logger.info("User updated: id=%d by=%s changes=%s", user_id, admin.username, body.model_dump(exclude_none=True))
    return UserResponse.model_validate(user)


# ─── Delete user ─────────────────────────────────────────────────────────────

@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    admin: CurrentUser = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a user (set status to disabled). Admin only."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    user.status = "disabled"
    logger.info("User disabled: id=%d username=%s by=%s", user_id, user.username, admin.username)
    return {"status": "disabled", "user_id": user_id}


# ─── Reset password (admin) ─────────────────────────────────────────────────

@router.post("/{user_id}/reset-password")
async def reset_password(
    user_id: int,
    body: ResetPasswordRequest,
    admin: CurrentUser = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Reset a user's password (admin only). Only for local auth users."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.auth_provider != "local":
        raise HTTPException(status_code=400, detail="Cannot reset password for federated user")

    errors = validate_password_policy(body.new_password)
    if errors:
        raise HTTPException(status_code=422, detail="; ".join(errors))

    user.hashed_password = hash_password(body.new_password)
    user.password_changed_at = datetime.now(timezone.utc)
    user.failed_login_count = 0
    user.status = "active"
    user.locked_until = None

    logger.info("Password reset: user=%s by=%s", user.username, admin.username)
    return {"status": "password_reset", "user_id": user_id}


# ─── Change own password (any authenticated user) ───────────────────────────

@router.post("/me/change-password")
async def change_my_password(
    body: ChangePasswordRequest,
    current_user: CurrentUser = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """Change your own password. Requires current password verification."""
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.auth_provider != "local":
        raise HTTPException(status_code=400, detail="Password change not available for federated accounts")

    from sia.auth.password import verify_password
    if not user.hashed_password or not verify_password(body.current_password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    errors = validate_password_policy(body.new_password)
    if errors:
        raise HTTPException(status_code=422, detail="; ".join(errors))

    user.hashed_password = hash_password(body.new_password)
    user.password_changed_at = datetime.now(timezone.utc)

    return {"status": "password_changed"}
