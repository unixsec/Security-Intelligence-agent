"""API Keys management endpoints (admin only).

Backs the front-end ApiKeys management view. The plaintext key is shown
**exactly once** at creation time; only the SHA-256 digest is persisted.
"""

from __future__ import annotations

import hashlib
import logging
import secrets as secrets_mod
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sia.auth.rbac import CurrentUser, require_role
from sia.common.database import get_db
from sia.models.api_key import APIKey

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api-keys",
    tags=["api-keys"],
    dependencies=[Depends(require_role("admin"))],
)


# ─── Schemas ──────────────────────────────────────────────────────────────

class APIKeyCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=64)
    role: str = Field("viewer")
    scopes: list[str] = Field(default_factory=lambda: ["*"])
    description: str | None = Field(None, max_length=255)
    expires_in_days: int | None = Field(None, ge=1, le=3650)

    @field_validator("role")
    @classmethod
    def _role(cls, v: str) -> str:
        if v not in ("admin", "analyst", "viewer"):
            raise ValueError("role must be admin / analyst / viewer")
        return v

    @field_validator("scopes")
    @classmethod
    def _scopes(cls, v: list[str]) -> list[str]:
        if not v:
            return ["*"]
        for s in v:
            if not isinstance(s, str) or not s:
                raise ValueError("scopes must be non-empty strings")
            # allow either '*' or path prefix '/api/v1/...'
            if s != "*" and not s.startswith("/"):
                raise ValueError("scope must be '*' or a path prefix starting with '/'")
        return v


class APIKeyResponse(BaseModel):
    id: int
    name: str
    role: str
    scopes: list[str]
    description: str | None
    created_at: datetime
    expires_at: datetime | None
    disabled: bool
    last_used_at: datetime | None
    created_by: str | None

    model_config = {"from_attributes": True}


class APIKeyCreateResponse(APIKeyResponse):
    """Returned only once at creation, with the plaintext key."""
    plaintext: str = Field(..., description="Plaintext key — shown ONCE; copy it now.")


# ─── List ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[APIKeyResponse])
async def list_keys(
    include_disabled: bool = True,
    db: AsyncSession = Depends(get_db),
):
    q = select(APIKey).order_by(APIKey.created_at.desc())
    if not include_disabled:
        q = q.where(APIKey.disabled == False)  # noqa: E712
    rows = (await db.execute(q)).scalars().all()
    return [APIKeyResponse.model_validate(r) for r in rows]


# ─── Create ───────────────────────────────────────────────────────────────

@router.post("", response_model=APIKeyCreateResponse, status_code=201)
async def create_key(
    body: APIKeyCreate,
    admin: CurrentUser = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Create a new API key. Plaintext is returned ONCE."""
    # Reject duplicate name
    existing = await db.execute(select(APIKey.id).where(APIKey.name == body.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Name already used")

    plaintext = "sia_" + secrets_mod.token_urlsafe(32)
    digest = hashlib.sha256(plaintext.encode()).hexdigest()
    expires_at = (
        datetime.now(timezone.utc) + timedelta(days=body.expires_in_days)
        if body.expires_in_days else None
    )

    row = APIKey(
        name=body.name,
        key_hash=digest,
        role=body.role,
        scopes=body.scopes,
        description=body.description,
        expires_at=expires_at,
        disabled=False,
        created_by=admin.username,
    )
    db.add(row)
    await db.flush()

    logger.info("API key created: name=%s role=%s by=%s", row.name, row.role, admin.username)
    resp = APIKeyResponse.model_validate(row).model_dump()
    return APIKeyCreateResponse(plaintext=plaintext, **resp)


# ─── Update / Revoke ──────────────────────────────────────────────────────

class APIKeyUpdate(BaseModel):
    disabled: bool | None = None
    description: str | None = None
    expires_in_days: int | None = Field(None, ge=0, le=3650)


@router.put("/{key_id}", response_model=APIKeyResponse)
async def update_key(
    key_id: int,
    body: APIKeyUpdate,
    admin: CurrentUser = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    row = (await db.execute(select(APIKey).where(APIKey.id == key_id))).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="key not found")
    if body.disabled is not None:
        row.disabled = body.disabled
    if body.description is not None:
        row.description = body.description
    if body.expires_in_days is not None:
        row.expires_at = (
            datetime.now(timezone.utc) + timedelta(days=body.expires_in_days)
            if body.expires_in_days > 0 else None
        )
    logger.info("API key updated: id=%d by=%s", key_id, admin.username)
    return APIKeyResponse.model_validate(row)


@router.delete("/{key_id}")
async def revoke_key(
    key_id: int,
    admin: CurrentUser = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Soft-revoke (sets disabled=true). The hash row stays so audit logs can resolve it."""
    row = (await db.execute(select(APIKey).where(APIKey.id == key_id))).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="key not found")
    row.disabled = True
    logger.info("API key revoked: id=%d name=%s by=%s", key_id, row.name, admin.username)
    return {"status": "revoked", "id": key_id}
