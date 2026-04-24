"""Push channel adapter contract + registry.

Every output channel (email, IM, SMS) subclasses `PushAdapter` and
registers with `@push_registry.register("<kind>")`. The dispatcher
(`sia.reporter.pusher.dispatcher`) iterates subscribers, picks their
preferred channel(s), builds one adapter instance per call, and awaits
`adapter.run(message)`.

Contract: one async `_do(self, message: PushMessage) -> PushResult`.

Security:
  * Credentials (bot tokens, webhook URLs with embedded secrets) MUST
    come from `/etc/sia/secrets/` via `resolve_secret()` — adapters never
    read `os.environ` directly.
  * Outbound URLs go through `url_validator.validate_source_url` to
    prevent SSRF via mis-configured webhooks pointing to internal hosts.
  * HMAC/JWT signatures are verified/generated per channel spec so the
    receiver can prove authenticity.

Reliability:
  * Adapters wrap network IO in `resilient_call(redis_breaker-or-custom,…)`
    for exponential backoff + circuit breaker.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from sia.adapters.base import AdapterConfig, AdapterError, BaseAdapter, Registry


@dataclass
class PushMessage:
    """Canonical payload handed to every push adapter.

    Channel adapters render this into channel-specific markdown/JSON/etc.
    `attachments` is a list of (filename, bytes, content_type) tuples; the
    dispatcher uploads them to MinIO separately if the channel can't carry
    inline binaries (telegram/SMS).
    """
    title: str
    body: str                         # plain text / markdown
    level: Literal["emergency", "high", "normal", "info"] = "normal"
    html_body: str | None = None
    url: str | None = None            # deep link back to SIA console
    tags: list[str] = field(default_factory=list)
    attachments: list[tuple[str, bytes, str]] = field(default_factory=list)
    recipients: list[str] = field(default_factory=list)   # channel-specific: email / openid / phone
    sent_at: datetime = field(default_factory=datetime.now)


@dataclass
class PushResult:
    """Result returned by every adapter. Dispatcher aggregates these."""
    channel: str                     # kind
    recipient: str                   # string for human readability
    accepted: bool                   # True iff the channel returned 2xx/ok
    external_id: str | None = None   # message id from the provider
    error: str | None = None


class PushAdapter(BaseAdapter):
    """Base class for push channels. Subclass + @push_registry.register."""

    async def _do(self, message: PushMessage) -> PushResult:  # type: ignore[override]
        raise NotImplementedError


push_registry: Registry[PushAdapter] = Registry("push")


# ─── Secret resolution helper ────────────────────────────────────────────

def resolve_secret(config_value: str) -> str:
    """Resolve a `${SIA_*}` reference or a `secret:<name>` token.

    Adapter config values are YAML strings. To avoid embedding real secrets
    in values files, config references a secret key; this helper pulls it
    from /etc/sia/secrets/<NAME> or os.environ[NAME] at runtime.
    """
    import os

    from sia.config import _resolve_secret as _rs  # reuse config.py resolver
    if not config_value:
        return ""
    if config_value.startswith("secret:"):
        name = config_value.removeprefix("secret:")
        return _rs(name) or ""
    if config_value.startswith("${") and config_value.endswith("}"):
        inner = config_value[2:-1]
        if ":-" in inner:
            var, default = inner.split(":-", 1)
            return os.environ.get(var, default)
        return _rs(inner) or os.environ.get(inner, "")
    return config_value


def _format_message(message: PushMessage, emoji_map: dict[str, str] | None = None) -> str:
    """Shared text renderer used by IM channels. Produces markdown-ish body."""
    em = (emoji_map or {}).get(message.level, "")
    head = f"{em} **{message.title}**".strip()
    parts = [head, "", message.body.strip()]
    if message.url:
        parts += ["", f"🔗 {message.url}"]
    if message.tags:
        parts.append("🏷 " + ", ".join(message.tags))
    return "\n".join(parts)
