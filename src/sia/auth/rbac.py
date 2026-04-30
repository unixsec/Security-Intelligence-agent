"""Role-Based Access Control — FastAPI dependencies."""

from __future__ import annotations

import hashlib
import logging
import os
import secrets
from datetime import datetime

import jwt as pyjwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from sia.auth.jwt import decode_token, is_token_revoked
from sia.common.database import get_db
from sia.config import get_auth_config, get_settings
from sia.models.api_key import APIKey
from sia.models.user import User

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)

# Role hierarchy: admin > analyst > viewer
ROLE_LEVEL = {"admin": 30, "analyst": 20, "viewer": 10}


class CurrentUser:
    """Resolved identity — attached to the request."""

    __slots__ = ("id", "username", "role", "auth_method")

    def __init__(self, *, id: int, username: str, role: str, auth_method: str):
        self.id = id
        self.username = username
        self.role = role
        self.auth_method = auth_method

    def has_role(self, required: str) -> bool:
        return ROLE_LEVEL.get(self.role, 0) >= ROLE_LEVEL.get(required, 0)


async def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    """Resolve the current user from Bearer JWT or legacy X-API-Key header.

    Priority: Bearer token > X-API-Key header.
    """
    auth_cfg = get_auth_config()

    # --- Path 1: Bearer JWT ---
    if creds and creds.credentials:
        try:
            payload = decode_token(creds.credentials)
        except pyjwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except pyjwt.PyJWTError:
            raise HTTPException(status_code=401, detail="Invalid token")

        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")

        # SEC-4: refuse explicitly revoked tokens (logout etc.).
        if await is_token_revoked(payload):
            raise HTTPException(status_code=401, detail="Token has been revoked")

        user_id = int(payload["sub"])
        # Verify user still active in DB
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user or user.status != "active":
            raise HTTPException(status_code=401, detail="User account is inactive")

        return CurrentUser(
            id=user.id,
            username=user.username,
            role=user.role,
            auth_method="jwt",
        )

    # --- Path 2: API Key ---
    api_key_cfg = auth_cfg.get("api_key", {})
    if api_key_cfg.get("enabled", True):
        header_name = api_key_cfg.get("header_name", "X-API-Key")
        api_key = request.headers.get(header_name)
        if api_key:
            return await _authenticate_api_key(api_key, request, db)

    # --- Path 3: Dev anonymous ---
    if get_settings().env == "dev":
        return CurrentUser(id=0, username="dev-anonymous", role="admin", auth_method="anonymous")

    raise HTTPException(
        status_code=401,
        detail="Authentication required. Provide Bearer token or X-API-Key header.",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def _authenticate_api_key(
    api_key: str, request: Request, db: AsyncSession
) -> CurrentUser:
    """SEC-2: validate the API key against the ``api_keys`` table.

    Resolution order:
      1. DB-stored key (preferred, scope-aware, revocable, expirable).
      2. Legacy ``SIA_API_KEY`` env var (admin + ``*`` scope; back-compat only).

    On match the row's ``last_used_at`` is updated best-effort.
    """
    digest = hashlib.sha256(api_key.encode()).hexdigest()

    # 1) DB lookup
    try:
        row_result = await db.execute(select(APIKey).where(APIKey.key_hash == digest))
        row: APIKey | None = row_result.scalar_one_or_none()
    except Exception:
        # If api_keys table is missing (fresh DB before alembic), fall through
        # to env fallback so installs can still bootstrap.
        logger.exception("APIKey lookup failed; falling back to env")
        row = None

    if row is not None:
        if row.disabled:
            raise HTTPException(status_code=401, detail="API key disabled")
        if row.expires_at and row.expires_at < datetime.utcnow():
            raise HTTPException(status_code=401, detail="API key expired")

        # Path-prefix scope check
        scopes = row.scopes or ["*"]
        path = request.url.path
        if "*" not in scopes and not any(path.startswith(s) for s in scopes):
            raise HTTPException(
                status_code=403,
                detail=f"API key not authorized for path {path}",
            )

        # Best-effort last-used stamp; never block the request on it.
        try:
            await db.execute(
                update(APIKey).where(APIKey.id == row.id).values(last_used_at=datetime.utcnow())
            )
        except Exception:
            logger.debug("Failed to update last_used_at for api key %s", row.name, exc_info=True)

        return CurrentUser(id=0, username=f"apikey:{row.name}", role=row.role, auth_method="api_key")

    # 2) Env fallback (single-key admin, back-compat)
    expected = os.environ.get("SIA_API_KEY", "")
    if not expected:
        # Refuse silent default: explicit configuration required.
        raise HTTPException(status_code=401, detail="API Key auth not configured")
    if not secrets.compare_digest(api_key, expected):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return CurrentUser(id=0, username="api-key", role="admin", auth_method="api_key")


def require_role(min_role: str):
    """FastAPI dependency factory — restrict endpoint to minimum role level.

    Usage:
        @router.get("/admin-only", dependencies=[Depends(require_role("admin"))])
    """

    async def _checker(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not user.has_role(min_role):
            raise HTTPException(
                status_code=403,
                detail=f"Requires role '{min_role}' or above. Your role: '{user.role}'",
            )
        return user

    return _checker
