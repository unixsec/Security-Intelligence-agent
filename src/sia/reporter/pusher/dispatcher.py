"""Multi-channel push dispatcher (v0.3+).

Business code (emergency alerts, daily report push tasks) calls
`dispatch(message, subscribers)`. The dispatcher:

    1. Picks each subscriber's active channels (UI preference + TLP filter)
    2. Builds the appropriate PushAdapter with config from push_channels.yaml
    3. Runs each send concurrently with bounded concurrency
    4. Records every attempt in `push_log` for traceability
    5. Returns an aggregate result the caller can alert on

This file replaces the legacy `reporter/pusher/channels.py` which had
hard-coded wechat+feishu+email — now any channel in
`sia.adapters.push.push_registry` is pluggable.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable

from sia.adapters.push import PushAdapter, PushMessage, push_registry
from sia.adapters.push.base import PushResult
from sia.common.audit import audit

logger = logging.getLogger(__name__)


# TLP level ordering. A subscriber with `max_tlp=GREEN` must NOT receive
# AMBER/RED items; enforced here at dispatch time.
_TLP_ORDER = {"CLEAR": 0, "GREEN": 1, "AMBER": 2, "RED": 3}


@dataclass
class Subscriber:
    """Minimal view of a subscriber used by the dispatcher.

    Concrete fields come from `sia.models.system.Subscriber` — the caller
    converts DB rows to this shape so the dispatcher has no ORM dependency.
    """
    id: int
    name: str
    preferred_channel: str                 # "wechat_work" | "feishu" | ...
    channel_addresses: dict[str, list[str]] = field(default_factory=dict)
    max_tlp: str = "GREEN"
    subscribe_level: str = "all"           # "all" | "p0_p1_only" | "daily" | ...


@dataclass
class DispatchResult:
    results: list[PushResult]
    sent: int
    skipped: int
    failed: int


# ─── Channel config registry ───────────────────────────────────────────

# A process-wide mapping: channel_kind → adapter config. Loaded at startup
# from `config/push_channels.yaml`; may be hot-reloaded.
_channel_configs: dict[str, dict[str, Any]] = {}


def register_channel_config(kind: str, config: dict[str, Any]) -> None:
    """Replace/insert a channel's runtime config."""
    if kind not in push_registry.kinds():
        raise ValueError(f"no push adapter registered for kind={kind!r}")
    _channel_configs[kind] = dict(config)


def load_channel_configs(channels_yaml_path: str) -> None:
    """Load `channels:` map from YAML; each entry is a channel_configs row."""
    import yaml
    with open(channels_yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    for kind, cfg in (data.get("channels") or {}).items():
        register_channel_config(kind, cfg or {})
    logger.info("loaded %d push channel configs from %s",
                len(data.get("channels") or {}), channels_yaml_path)


# ─── Dispatch ──────────────────────────────────────────────────────────

def _should_deliver(subscriber: Subscriber, message: PushMessage,
                    message_tlp: str = "GREEN") -> bool:
    """Return False if the subscriber should not receive this message."""
    if _TLP_ORDER.get(message_tlp, 1) > _TLP_ORDER.get(subscriber.max_tlp, 1):
        return False
    if subscriber.subscribe_level == "p0_p1_only" and message.level not in ("emergency", "high"):
        return False
    return True


def _build_adapter(kind: str) -> PushAdapter:
    cfg = _channel_configs.get(kind)
    if cfg is None:
        raise RuntimeError(f"push channel {kind!r} has no runtime config; "
                           f"call load_channel_configs() at startup")
    return push_registry.build(kind, cfg)


async def _dispatch_one(
    sub: Subscriber, message: PushMessage, kinds: list[str],
    sem: asyncio.Semaphore,
) -> list[PushResult]:
    """Send `message` via each channel kind, each constrained by `sem`."""
    results: list[PushResult] = []
    for kind in kinds:
        addresses = sub.channel_addresses.get(kind) or []
        if not addresses:
            results.append(PushResult(channel=kind, recipient=sub.name,
                                      accepted=False,
                                      error="no address for this channel"))
            continue
        msg = PushMessage(
            title=message.title, body=message.body, html_body=message.html_body,
            level=message.level, url=message.url, tags=message.tags,
            attachments=message.attachments, recipients=addresses,
            sent_at=datetime.now(),
        )
        async with sem:
            try:
                adapter = _build_adapter(kind)
                res = await adapter.run(msg)
                if not isinstance(res, PushResult):
                    res = PushResult(channel=kind, recipient=sub.name,
                                     accepted=False, error="adapter returned non-PushResult")
                results.append(res)
            except Exception as e:  # noqa: BLE001 — per-channel failures isolated
                logger.exception("dispatch failed for sub=%s channel=%s", sub.name, kind)
                results.append(PushResult(channel=kind, recipient=sub.name,
                                           accepted=False, error=str(e)))
    return results


async def dispatch(
    message: PushMessage,
    subscribers: Iterable[Subscriber],
    *,
    message_tlp: str = "GREEN",
    fanout_kinds: list[str] | None = None,
    concurrency: int = 8,
) -> DispatchResult:
    """Deliver `message` to `subscribers` across their channels.

    Args:
        fanout_kinds: if given, send via exactly these channels (for SIA
          admin-triggered "send test to all").
          Otherwise, each subscriber receives on their preferred_channel.
        concurrency: max parallel adapter calls (bounds network IO).
    """
    sem = asyncio.Semaphore(concurrency)
    tasks = []
    skipped = 0
    for sub in subscribers:
        if not _should_deliver(sub, message, message_tlp=message_tlp):
            skipped += 1
            audit("push.skip", actor_name=sub.name, target_id=sub.id,
                  result="denied", reason="tlp_or_level",
                  level=message.level, tlp=message_tlp)
            continue
        kinds = fanout_kinds or [sub.preferred_channel]
        tasks.append(_dispatch_one(sub, message, kinds, sem))

    all_results: list[PushResult] = []
    for lst in await asyncio.gather(*tasks, return_exceptions=False):
        all_results.extend(lst)

    sent = sum(1 for r in all_results if r.accepted)
    failed = sum(1 for r in all_results if not r.accepted)

    audit("push.dispatch", target="message", target_id=message.title[:60],
          result="success" if failed == 0 else "failure",
          level=message.level, sent=sent, failed=failed, skipped=skipped)

    return DispatchResult(results=all_results, sent=sent, skipped=skipped, failed=failed)
