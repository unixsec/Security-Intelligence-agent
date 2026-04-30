"""Resource-level permissions (v0.4-3).

Why
---
Endpoint-level RBAC (``require_role("admin")``) is too coarse for
multi-team deployments. Examples that v0.3 cannot express:

* "User Bob in team-soc can read intel from sources owned by team-soc but
  not from team-appsec sources."
* "API key ``incident-bot`` can mark intel as ``reviewed`` but cannot
  delete reports."
* "Auditor role can read everything but cannot mutate anything."

Model
-----
* **Permission tuple** = ``(resource, action)``, e.g.
  ``("intelligence", "read")``, ``("reports", "generate")``,
  ``("sources", "create")``.
* **Role** maps to a set of permission tuples (``ROLE_PERMS`` below).
* **Group** (DB row) supplements the role with extra permissions and / or
  resource ownership filters (e.g. "only sources where ``team_id`` matches").
* The decorator ``@require_permission(resource, action)`` does the check;
  it falls back to the legacy role hierarchy when no explicit permission
  matrix is configured.

Backwards compatibility
-----------------------
The existing ``require_role(min_role)`` keeps working — it's a wrapper that
maps to the equivalent permission tuple for that endpoint (kept for the
migration window; new endpoints should use ``require_permission`` directly).
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass

from fastapi import Depends, HTTPException

logger = logging.getLogger(__name__)


# ─── Permission catalog ──────────────────────────────────────────────────

# Canonical resource names — keep stable, log-grep friendly.
RESOURCES = (
    "intelligence",      # /api/v1/intelligence/*
    "reports",           # /api/v1/reports/*
    "sources",           # /api/v1/sources/*
    "users",             # /api/v1/users/*
    "system",            # /api/v1/system/*
    "audit",             # /api/v1/audit/*  (v0.4)
)

ACTIONS = (
    "read", "create", "update", "delete",
    "review",       # mark item as reviewed
    "generate",     # generate report
    "trigger",      # trigger a collection / re-analyze
    "manage",       # any mutation including settings
)


@dataclass(frozen=True)
class Permission:
    resource: str
    action: str

    def __str__(self) -> str:
        return f"{self.resource}:{self.action}"


def perm(resource: str, action: str) -> Permission:
    return Permission(resource=resource, action=action)


# Role baseline — exact permissions of each role.
# Resource owners (the "groups" feature below) layer additions on top.
ROLE_PERMS: dict[str, set[Permission]] = {
    # admin: anything goes.
    "admin": {perm(r, a) for r in RESOURCES for a in ACTIONS},
    # analyst: read+review+generate; cannot manage users / delete sources.
    "analyst": (
        {perm("intelligence", a) for a in ("read", "review")}
        | {perm("reports", a) for a in ("read", "generate")}
        | {perm("sources", a) for a in ("read", "trigger")}
        | {perm("system", "read")}
        | {perm("audit", "read")}
    ),
    # viewer: read-only across the board.
    "viewer": (
        {perm("intelligence", "read")}
        | {perm("reports", "read")}
        | {perm("sources", "read")}
        | {perm("system", "read")}
    ),
}


def role_has(role: str, p: Permission) -> bool:
    return p in ROLE_PERMS.get(role, set())


# ─── Subject (user / api-key) wrapper ───────────────────────────────────


def has_permission(subject: object, resource: str, action: str) -> bool:
    """``subject`` is a CurrentUser or an APIKey-shaped object.

    Resolution:
        1. role baseline grants
        2. ``subject.extra_permissions`` (set[Permission]) — DB-loaded extras
        3. ``subject.scopes`` strict prefix match (the legacy /api/v1/...
           scope used by API keys; any path-prefix scope grants the
           equivalent permission for that resource)
    """
    p = perm(resource, action)
    role = getattr(subject, "role", "viewer")
    if role_has(role, p):
        return True

    extra = getattr(subject, "extra_permissions", None) or set()
    if p in extra:
        return True

    scopes = getattr(subject, "scopes", None) or []
    # ``["*"]`` means full path-prefix wildcard; otherwise an entry like
    # ``"/api/v1/reports/"`` grants reports:* permissions.
    if "*" in scopes:
        return True
    for scope in scopes:
        if not isinstance(scope, str):
            continue
        if scope.rstrip("/").endswith(f"/{resource}"):
            return True
        if scope.rstrip("/") == f"/api/v1/{resource}":
            return True
    return False


# ─── FastAPI dependency factory ──────────────────────────────────────────


def require_permission(resource: str, action: str):
    """FastAPI dependency:

    ``router.get("/x", dependencies=[Depends(require_permission("reports", "generate"))])``
    """
    from sia.auth.rbac import CurrentUser, get_current_user

    async def _check(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not has_permission(user, resource, action):
            raise HTTPException(
                status_code=403,
                detail=f"Permission '{resource}:{action}' required (role={user.role})",
            )
        return user

    return _check


# ─── Group model helpers ────────────────────────────────────────────────


def merge_permissions(*sources: Iterable[Permission]) -> set[Permission]:
    """Compose multiple permission iterables into a single set."""
    out: set[Permission] = set()
    for s in sources:
        out.update(s)
    return out
