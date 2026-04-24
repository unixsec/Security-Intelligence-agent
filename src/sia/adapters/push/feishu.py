"""飞书 (Feishu / Lark) bot webhook push with signed request.

Config::
    kind: feishu
    webhook: "secret:SIA_FEISHU_WEBHOOK"
    signing_secret: "secret:SIA_FEISHU_SIGN"    # optional HMAC
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time

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

_COLOR = {"emergency": "red", "high": "orange", "normal": "blue", "info": "grey"}


def _sign(secret: str, ts: int) -> str:
    key = f"{ts}\n{secret}".encode("utf-8")
    digest = hmac.new(key, b"", hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


@push_registry.register("feishu")
class FeishuPusher(PushAdapter):
    async def _do(self, message: PushMessage) -> PushResult:
        webhook = resolve_secret(self.cfg.require("webhook", str))
        sign_secret = resolve_secret(self.cfg.opt("signing_secret", ""))
        if not webhook:
            return PushResult(channel="feishu", recipient="robot",
                              accepted=False, error="webhook empty")
        validate_source_url(webhook)

        # Interactive Card for richer rendering
        card = {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {
                    "template": _COLOR.get(message.level, "blue"),
                    "title": {"tag": "plain_text",
                              "content": f"{_EMOJI.get(message.level, '')} {message.title}"},
                },
                "elements": [
                    {"tag": "markdown", "content": message.body[:5000]},
                ],
            },
        }
        if message.url:
            card["card"]["elements"].append({
                "tag": "action",
                "actions": [{
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "查看详情"},
                    "url": message.url,
                    "type": "primary",
                }],
            })

        payload: dict = card
        if sign_secret:
            ts = int(time.time())
            payload = {"timestamp": str(ts), "sign": _sign(sign_secret, ts), **card}

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(webhook, json=payload)
        body = resp.json() if resp.content else {}
        ok = resp.status_code == 200 and body.get("StatusCode", body.get("code")) in (0, None)
        return PushResult(
            channel="feishu",
            recipient="robot",
            accepted=ok,
            external_id=body.get("data", {}).get("message_id") if ok else None,
            error=None if ok else f"HTTP {resp.status_code}: {resp.text[:200]}",
        )
