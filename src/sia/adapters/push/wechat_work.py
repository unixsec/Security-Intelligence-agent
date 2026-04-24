"""企业微信 (WeCom) robot webhook push.

Config::
    kind: wechat_work
    webhook: "secret:SIA_WECHAT_WORK_WEBHOOK"
    # For private-message (server-app) flows, set agent_id/corp_id/secret instead.

Robot webhook API: https://developer.work.weixin.qq.com/document/path/91770
"""

from __future__ import annotations

import httpx

from sia.adapters.push.base import (
    PushAdapter,
    PushMessage,
    PushResult,
    _format_message,
    push_registry,
    resolve_secret,
)
from sia.collector.url_validator import validate_source_url

_EMOJI = {"emergency": "🚨", "high": "⚠️", "normal": "📢", "info": "ℹ️"}


@push_registry.register("wechat_work")
class WeChatWorkPusher(PushAdapter):
    async def _do(self, message: PushMessage) -> PushResult:
        webhook = resolve_secret(self.cfg.require("webhook", str))
        if not webhook:
            return PushResult(channel="wechat_work", recipient="robot",
                              accepted=False, error="webhook empty")
        validate_source_url(webhook)

        text = _format_message(message, _EMOJI)
        payload = {"msgtype": "markdown", "markdown": {"content": text}}
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(webhook, json=payload)
        ok = resp.status_code == 200 and resp.json().get("errcode") == 0
        return PushResult(
            channel="wechat_work",
            recipient=",".join(message.recipients) or "robot",
            accepted=ok,
            external_id=resp.json().get("msgid") if ok else None,
            error=None if ok else f"HTTP {resp.status_code}: {resp.text[:200]}",
        )
