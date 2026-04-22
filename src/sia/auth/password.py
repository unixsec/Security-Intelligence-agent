"""Password hashing and policy enforcement."""

from __future__ import annotations

import re

from passlib.context import CryptContext

from sia.config import get_auth_config

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return _pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_ctx.verify(plain, hashed)


def validate_password_policy(password: str) -> list[str]:
    """Return list of policy violation messages (empty = OK)."""
    cfg = get_auth_config().get("password", {})
    errors: list[str] = []

    min_len = cfg.get("min_length", 8)
    if len(password) < min_len:
        errors.append(f"Password must be at least {min_len} characters")
    if cfg.get("require_uppercase", True) and not re.search(r"[A-Z]", password):
        errors.append("Password must contain at least one uppercase letter")
    if cfg.get("require_lowercase", True) and not re.search(r"[a-z]", password):
        errors.append("Password must contain at least one lowercase letter")
    if cfg.get("require_digit", True) and not re.search(r"\d", password):
        errors.append("Password must contain at least one digit")
    if cfg.get("require_special", False) and not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        errors.append("Password must contain at least one special character")

    return errors
