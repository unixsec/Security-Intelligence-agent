"""Role-Based Access Control — FastAPI dependencies."""

from __future__ import annotations

import logging
import os
import secrets

import jwt as pyjwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sia.auth.jwt import decode_token
from sia.common.database import get_db
from sia.config import get_auth_config, get_settings
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

    # --- Path 2: Legacy API Key ---
    api_key_cfg = auth_cfg.get("api_key", {})
    if api_key_cfg.get("enabled", True):
        header_name = api_key_cfg.get("header_name", "X-API-Key")
        api_key = request.headers.get(header_name)
        if api_key:
            expected = os.environ.get("SIA_API_KEY", "")
            if not expected:
                # Previously a literal dev default was used. That meant anyone
                # who knew the string could authenticate, even in tests that
                # accidentally ran against a dev instance. Require an explicit
                # SIA_API_KEY to be set; otherwise fail closed.
                raise HTTPException(status_code=401, detail="API Key auth not configured")

            if not secrets.compare_digest(api_key, expected):
                raise HTTPException(status_code=401, detail="Invalid API key")

            # API key grants admin access (it's a service key)
            return CurrentUser(id=0, username="api-key", role="admin", auth_method="api_key")

    # --- Path 3: Dev anonymous ---
    if get_settings().env == "dev":
        return CurrentUser(id=0, username="dev-anonymous", role="admin", auth_method="anonymous")

    raise HTTPException(
        status_code=401,
        detail="Authentication required. Provide Bearer token or X-API-Key header.",
        headers={"WWW-Authenticate": "Bearer"},
    )


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
