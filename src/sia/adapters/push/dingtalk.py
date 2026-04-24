"""钉钉 (DingTalk) bot webhook with HMAC signature.

Config::
    kind: dingtalk
    webhook: "secret:SIA_DINGTALK_WEBHOOK"
    secret:  "secret:SIA_DINGTALK_SECRET"       # required for 'sign' 安全设置
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
import urllib.parse

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


def _sign(secret: str) -> tuple[str, str]:
    ts = str(round(time.time() * 1000))
    string_to_sign = f"{ts}\n{secret}"
    digest = hmac.new(secret.encode("utf-8"),
                      string_to_sign.encode("utf-8"),
                      hashlib.sha256).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(digest).decode("utf-8"))
    return ts, sign


@push_registry.register("dingtalk")
class DingTalkPusher(PushAdapter):
    async def _do(self, message: PushMessage) -> PushResult:
        webhook = resolve_secret(self.cfg.require("webhook", str))
        secret = resolve_secret(self.cfg.opt("secret", ""))
        if not webhook:
            return PushResult(channel="dingtalk", recipient="robot",
                              accepted=False, error="webhook empty")
        validate_source_url(webhook)

        if secret:
            ts, sign = _sign(secret)
            webhook = f"{webhook}&timestamp={ts}&sign={sign}"

        text = _format_message(message, _EMOJI)
        payload = {
            "msgtype": "markdown",
            "markdown": {"title": message.title[:40] or "SIA alert", "text": text},
        }
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(webhook, json=payload)
        body = resp.json() if resp.content else {}
        ok = resp.status_code == 200 and body.get("errcode") == 0
        return PushResult(
            channel="dingtalk",
            recipient="robot",
            accepted=ok,
            error=None if ok else f"HTTP {resp.status_code}: errcode={body.get('errcode')} {body.get('errmsg', '')[:120]}",
        )
