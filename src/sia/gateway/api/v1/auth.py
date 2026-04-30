"""Authentication API endpoints — login, logout, token refresh, OIDC flow."""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from sia.auth.jwt import create_access_token, create_refresh_token, decode_token, token_hash
from sia.auth.password import verify_password
from sia.auth.rbac import CurrentUser, get_current_user
from sia.common.audit import audit
from sia.common.database import get_db
from sia.config import get_auth_config
from sia.models.user import RefreshToken, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


# ─── Request / Response schemas ──────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str
    provider: str = "local"   # "local" | "ldap"


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserBrief
    password_change_required: bool = False   # True for initial-password users


class UserBrief(BaseModel):
    id: int
    username: str
    display_name: str
    role: str
    auth_provider: str

    model_config = {"from_attributes": True}


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


def _assert_password_policy(password: str, policy: dict) -> None:
    """Enforce configured password policy; raise HTTPException on violation.

    Policy keys (see config/auth.yaml):
      min_length, require_uppercase, require_lowercase, require_digit,
      require_special.
    """
    min_length = policy.get("min_length", 8)
    if len(password) < min_length:
        raise HTTPException(status_code=400,
                            detail=f"Password must be at least {min_length} characters.")
    if policy.get("require_uppercase", True) and not any(c.isupper() for c in password):
        raise HTTPException(status_code=400,
                            detail="Password must contain an uppercase letter.")
    if policy.get("require_lowercase", True) and not any(c.islower() for c in password):
        raise HTTPException(status_code=400,
                            detail="Password must contain a lowercase letter.")
    if policy.get("require_digit", True) and not any(c.isdigit() for c in password):
        raise HTTPException(status_code=400,
                            detail="Password must contain a digit.")
    if policy.get("require_special", False) and not any(
        c in "!@#$%^&*()-_=+[]{};:'\",.<>/?`~\\|" for c in password
    ):
        raise HTTPException(status_code=400,
                            detail="Password must contain a special character.")


# Reorder for forward reference
TokenResponse.model_rebuild()


# ─── Login ───────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate with username/password (local or LDAP)."""
    auth_cfg = get_auth_config()
    lockout_cfg = auth_cfg.get("lockout", {})
    max_attempts = lockout_cfg.get("max_failed_attempts", 5)

    if body.provider == "ldap":
        return await _login_ldap(body, request, db)

    # --- Local authentication ---
    result = await db.execute(
        select(User).where(User.username == body.username, User.auth_provider == "local")
    )
    user = result.scalar_one_or_none()

    if not user:
        audit("user.login", actor_name=body.username, result="failure",
              reason="unknown_user", request=request)
        raise HTTPException(status_code=401, detail="Invalid username or password")

    if user.status == "locked":
        if user.locked_until and user.locked_until.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
            raise HTTPException(status_code=423, detail="Account is locked. Try again later.")
        # Lockout expired — reset
        user.status = "active"
        user.failed_login_count = 0

    if user.status != "active":
        raise HTTPException(status_code=403, detail="Account is disabled")

    if not user.hashed_password or not verify_password(body.password, user.hashed_password):
        user.failed_login_count += 1
        if user.failed_login_count >= max_attempts:
            from datetime import timedelta
            user.status = "locked"
            user.locked_until = datetime.now(timezone.utc) + timedelta(
                minutes=lockout_cfg.get("lockout_duration_minutes", 30)
            )
            logger.warning("Account locked: user=%s attempts=%d", user.username, user.failed_login_count)
        # Persist the failed-attempt state before raising, otherwise the
        # exception handler in get_db() will roll back the increment and
        # lockout, enabling unlimited password guessing.
        await db.commit()
        audit("user.login", actor_id=user.id, actor_name=user.username,
              result="failure", reason="bad_password",
              failed_count=user.failed_login_count, request=request)
        raise HTTPException(status_code=401, detail="Invalid username or password")

    # Success — reset failed count
    user.failed_login_count = 0
    user.last_login_at = datetime.now(timezone.utc)

    audit("user.login", actor_id=user.id, actor_name=user.username,
          result="success", provider="local", request=request)

    # First-login password change signal (SEC: seed admin must rotate)
    response = await _issue_tokens(user, request, db)
    if user.password_changed_at is None:
        response.password_change_required = True
    return response


async def _login_ldap(
    body: LoginRequest, request: Request, db: AsyncSession
) -> TokenResponse:
    """Authenticate via LDAP, auto-create local user if needed."""
    from sia.auth.providers.ldap import get_ldap_provider

    provider = get_ldap_provider()
    if not provider.enabled:
        raise HTTPException(status_code=400, detail="LDAP authentication is not enabled")

    try:
        info = provider.authenticate(body.username, body.password)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    # Find or create local user
    result = await db.execute(
        select(User).where(User.external_id == info.external_id, User.auth_provider == "ldap")
    )
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            username=info.username,
            email=info.email,
            display_name=info.display_name,
            role=info.role,
            auth_provider="ldap",
            external_id=info.external_id,
            status="active",
        )
        db.add(user)
        await db.flush()
        logger.info("LDAP user auto-created: %s role=%s", info.username, info.role)
    else:
        # Sync attributes on each login
        user.display_name = info.display_name
        user.email = info.email
        user.role = info.role

    user.last_login_at = datetime.now(timezone.utc)
    return await _issue_tokens(user, request, db)


# ─── OIDC flow ───────────────────────────────────────────────────────────────

@router.get("/oidc/providers")
async def list_oidc_providers():
    """List available OIDC providers for the login page."""
    from sia.auth.providers.oidc import get_oidc_provider
    provider = get_oidc_provider()
    if not provider.enabled:
        return {"providers": []}
    return {"providers": provider.list_providers()}


@router.get("/oidc/authorize")
async def oidc_authorize(
    provider: str = Query(..., description="OIDC provider key"),
    redirect_uri: str = Query(..., description="Frontend callback URL"),
):
    """Redirect user to IdP authorization page."""
    from sia.auth.providers.oidc import get_oidc_provider

    oidc = get_oidc_provider()
    if not oidc.enabled:
        raise HTTPException(status_code=400, detail="OIDC is not enabled")

    state = secrets.token_urlsafe(32)
    url = await oidc.get_authorization_url(provider, redirect_uri, state)
    return {"authorization_url": url, "state": state}


@router.post("/oidc/callback")
async def oidc_callback(
    provider: str = Query(...),
    code: str = Query(...),
    redirect_uri: str = Query(...),
    state: str = Query(..., description="The state token returned by /oidc/authorize; required for PKCE."),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """Exchange OIDC authorization code for SIA tokens (PKCE-bound)."""
    from sia.auth.providers.oidc import get_oidc_provider

    oidc = get_oidc_provider()
    if not oidc.enabled:
        raise HTTPException(status_code=400, detail="OIDC is not enabled")

    try:
        info = await oidc.handle_callback(provider, redirect_uri, code, state=state)
    except ValueError as e:
        # Verifier missing/expired or userinfo non-2xx — explicit 4xx.
        logger.warning("OIDC callback rejected: %s", e)
        raise HTTPException(status_code=401, detail=str(e))
    except Exception:
        logger.exception("OIDC callback failed for provider=%s", provider)
        raise HTTPException(status_code=401, detail="OIDC authentication failed")

    # Find or create local user
    result = await db.execute(
        select(User).where(
            User.external_id == info.external_id,
            User.auth_provider == "oidc",
            User.oidc_issuer == info.issuer,
        )
    )
    user = result.scalar_one_or_none()

    pcfg = oidc.get_provider_config(info.provider_key)

    if not user:
        if not pcfg.get("auto_create_user", True):
            raise HTTPException(status_code=403, detail="User not provisioned. Contact admin.")

        user = User(
            username=info.username,
            email=info.email,
            display_name=info.display_name,
            role=info.role or pcfg.get("default_role", "viewer"),
            auth_provider="oidc",
            external_id=info.external_id,
            oidc_issuer=info.issuer,
            status="active",
        )
        db.add(user)
        await db.flush()
        logger.info("OIDC user auto-created: %s provider=%s", info.username, info.provider_key)
    else:
        # Sync attributes
        user.display_name = info.display_name
        user.email = info.email
        if info.role:
            user.role = info.role

    user.last_login_at = datetime.now(timezone.utc)
    return await _issue_tokens(user, request, db)


# ─── Token refresh ───────────────────────────────────────────────────────────

@router.post("/token/refresh", response_model=TokenResponse)
async def refresh_token(
    body: RefreshRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Exchange a refresh token for a new access + refresh token pair."""
    try:
        payload = decode_token(body.refresh_token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Not a refresh token")

    # Check revocation
    th = token_hash(body.refresh_token)
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == th)
    )
    stored = result.scalar_one_or_none()
    if not stored or stored.revoked:
        raise HTTPException(status_code=401, detail="Refresh token revoked")

    # Mark old token as revoked
    stored.revoked = True

    # Load user
    user_id = int(payload["sub"])
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or user.status != "active":
        raise HTTPException(status_code=401, detail="User account inactive")

    return await _issue_tokens(user, request, db)


# ─── Logout ──────────────────────────────────────────────────────────────────

class LogoutRequest(BaseModel):
    refresh_token: str | None = None
    access_token: str | None = None


@router.post("/logout")
async def logout(
    body: LogoutRequest,
    db: AsyncSession = Depends(get_db),
):
    """Revoke the supplied refresh token (DB) and access token (Redis blacklist).

    SEC-4: an access token has a short TTL but is otherwise stateless. We
    insert its ``jti`` into the ``jwt:revoked:`` set with TTL == remaining
    life so every subsequent request is rejected by ``is_token_revoked``.
    """
    if body.refresh_token:
        th = token_hash(body.refresh_token)
        await db.execute(
            update(RefreshToken).where(RefreshToken.token_hash == th).values(revoked=True)
        )

    if body.access_token:
        from sia.auth.jwt import revoke_token
        try:
            await revoke_token(body.access_token)
        except Exception:
            logger.exception("Failed to revoke access token via Redis")

    return {"status": "logged_out"}


# ─── Current user info ───────────────────────────────────────────────────────

@router.get("/me", response_model=UserBrief)
async def get_me(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the currently authenticated user's profile."""
    if current_user.auth_method == "api_key":
        return UserBrief(
            id=0, username="api-key", display_name="API Key", role="admin", auth_provider="api_key"
        )
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserBrief.model_validate(user)


# ─── Helpers ─────────────────────────────────────────────────────────────────

async def _issue_tokens(
    user: User, request: Request | None, db: AsyncSession
) -> TokenResponse:
    """Issue access + refresh tokens and persist refresh token."""
    auth_cfg = get_auth_config()
    jwt_cfg = auth_cfg.get("jwt", {})

    access = create_access_token(user.id, user.username, user.role)
    refresh, expires_at = create_refresh_token(user.id)

    # Persist refresh token hash
    db.add(RefreshToken(
        user_id=user.id,
        token_hash=token_hash(refresh),
        expires_at=expires_at,
        user_agent=request.headers.get("user-agent", "")[:500] if request else None,
        ip_address=request.client.host if request and request.client else None,
    ))

    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=jwt_cfg.get("access_token_expire_minutes", 30) * 60,
        user=UserBrief.model_validate(user),
    )


# ─── Change password ─────────────────────────────────────────────────────────

@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change the authenticated user's password.

    Required first-login flow: seed admin has `password_changed_at = NULL`;
    `/login` returns `password_change_required: true` and every authenticated
    endpoint returns 451 until the user calls this endpoint to rotate.
    """
    from sia.auth.password import hash_password, verify_password

    # Only local accounts can change passwords; LDAP/OIDC users must rotate
    # via their IdP.
    db_user = (await db.execute(
        select(User).where(User.id == user.id)
    )).scalar_one_or_none()
    if not db_user or db_user.auth_provider != "local":
        audit("user.password_change", actor_id=user.id, actor_name=user.username,
              result="denied", reason="not_local", request=request)
        raise HTTPException(
            status_code=400,
            detail="Password change not available for federated accounts.",
        )

    if not db_user.hashed_password or not verify_password(
        body.old_password, db_user.hashed_password
    ):
        audit("user.password_change", actor_id=user.id, actor_name=user.username,
              result="failure", reason="bad_old_password", request=request)
        raise HTTPException(status_code=401, detail="Old password incorrect.")

    if body.old_password == body.new_password:
        raise HTTPException(status_code=400,
                            detail="New password must differ from old.")

    auth_cfg = get_auth_config()
    _assert_password_policy(body.new_password, auth_cfg.get("password", {}))

    db_user.hashed_password = hash_password(body.new_password)
    db_user.password_changed_at = datetime.now(timezone.utc)
    await db.commit()

    # Revoke existing refresh tokens; user must re-login on other devices.
    from sqlalchemy import update as sql_update
    await db.execute(
        sql_update(RefreshToken)
        .where(RefreshToken.user_id == db_user.id, RefreshToken.revoked == False)  # noqa: E712
        .values(revoked=True)
    )
    await db.commit()

    audit("user.password_change", actor_id=user.id, actor_name=user.username,
          result="success", request=request)
    return {"status": "ok", "message": "Password changed. Existing sessions revoked."}
