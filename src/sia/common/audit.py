"""Structured audit logger (SEC-013).

Emits JSON audit events to a dedicated logger so they can be shipped to a
central SIEM/Loki pipeline separately from app logs.

Usage:
    from sia.common.audit import audit

    audit(
        "user.login",
        actor_id=user.id, actor_name=user.username,
        target="user",   target_id=user.id,
        result="success", request=request,
    )
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

# A dedicated logger so operators can route audit events to a separate file/sink.
_logger = logging.getLogger("sia.audit")
_logger.propagate = False  # don't duplicate to root
if not _logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(_h)
    _logger.setLevel(logging.INFO)


def audit(
    event: str,
    *,
    actor_id: int | None = None,
    actor_name: str | None = None,
    target: str | None = None,
    target_id: int | str | None = None,
    result: str = "success",
    request: Any = None,
    **extra: Any,
) -> None:
    """Emit a single audit event as one-line JSON.

    Fields:
        event      — dotted event name, e.g. "user.login" / "report.export"
        actor_id   — acting principal (user id or 0 for API-key service accts)
        actor_name — principal username for readability
        target     — resource type, e.g. "intelligence", "user"
        target_id  — id of the resource being acted on
        result     — "success" | "failure" | "denied"
        request    — optional FastAPI/Starlette Request for ip + path + ua
        extra      — any additional JSON-serializable context
    """
    payload: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "event": event,
        "result": result,
    }
    if actor_id is not None:
        payload["actor_id"] = actor_id
    if actor_name is not None:
        payload["actor_name"] = actor_name
    if target is not None:
        payload["target"] = target
    if target_id is not None:
        payload["target_id"] = target_id

    if request is not None:
        try:
            payload["ip"] = _client_ip(request)
            payload["path"] = request.url.path
            payload["method"] = request.method
            ua = request.headers.get("user-agent")
            if ua:
                payload["ua"] = ua[:200]
        except Exception:
            pass

    if extra:
        # Protect: never accept raw passwords/tokens by convention.
        for k in list(extra.keys()):
            if any(s in k.lower() for s in ("password", "secret", "token", "api_key")):
                extra[k] = "***REDACTED***"
        payload.update(extra)

    _logger.info(json.dumps(payload, ensure_ascii=False, default=str))


def _client_ip(request: Any) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"
