"""JWT access & refresh token management.

Supports both HS256 (symmetric; simple, dev default) and RS256 (asymmetric;
recommended for production so the verification key can be distributed without
granting sign capability). SEC-014.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import logging
from datetime import datetime, timedelta, timezone

import jwt

from sia.config import get_auth_config, get_settings

logger = logging.getLogger(__name__)


def _cfg() -> dict:
    return get_auth_config().get("jwt", {})


def _algorithm() -> str:
    # Config value wins; fallback to settings.auth for K8s-injected env var.
    cfg = _cfg()
    alg = cfg.get("algorithm")
    if not alg or alg.startswith("${"):
        alg = get_settings().auth.jwt_algorithm or "HS256"
    return alg


def _maybe_b64_decode(val: str) -> str:
    """Accept either a raw PEM string or a base64-encoded PEM."""
    if not val:
        return val
    s = val.strip()
    if s.startswith("-----BEGIN"):
        return s
    try:
        decoded = base64.b64decode(s, validate=True).decode("utf-8")
        if decoded.lstrip().startswith("-----BEGIN"):
            return decoded
    except (ValueError, binascii.Error, UnicodeDecodeError):
        pass
    return s


def _signing_key() -> str:
    alg = _algorithm()
    if alg == "RS256":
        priv = get_settings().auth.jwt_private_key or ""
        if not priv:
            raise RuntimeError("RS256 selected but SIA_AUTH_JWT_PRIVATE_KEY is empty")
        return _maybe_b64_decode(priv)
    # HS256 (or anything else symmetric) — fall back to shared secret
    secret = _cfg().get("secret_key") or get_settings().auth.jwt_secret or ""
    if not secret:
        raise RuntimeError("JWT secret not configured")
    return secret


def _verification_key() -> str:
    alg = _algorithm()
    if alg == "RS256":
        pub = get_settings().auth.jwt_public_key or ""
        if not pub:
            raise RuntimeError("RS256 selected but SIA_AUTH_JWT_PUBLIC_KEY is empty")
        return _maybe_b64_decode(pub)
    return _signing_key()


def create_access_token(
    user_id: int,
    username: str,
    role: str,
    extra: dict | None = None,
) -> str:
    cfg = _cfg()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=cfg.get("access_token_expire_minutes", 30)
    )
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "type": "access",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, _signing_key(), algorithm=_algorithm())


def create_refresh_token(user_id: int) -> tuple[str, datetime]:
    """Return (token_string, expires_at)."""
    cfg = _cfg()
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=cfg.get("refresh_token_expire_days", 7)
    )
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "exp": expires_at,
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(payload, _signing_key(), algorithm=_algorithm())
    return token, expires_at


def decode_token(token: str) -> dict:
    """Decode and validate a JWT. Raises jwt.PyJWTError on failure."""
    return jwt.decode(token, _verification_key(), algorithms=[_algorithm()])


def token_hash(token: str) -> str:
    """SHA-256 hash of a token for DB storage (never store raw tokens)."""
    return hashlib.sha256(token.encode()).hexdigest()
