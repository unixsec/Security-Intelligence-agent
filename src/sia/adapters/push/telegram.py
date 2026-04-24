"""Telegram Bot API push adapter.

Config::
    kind: telegram
    bot_token: "secret:SIA_TELEGRAM_BOT_TOKEN"
    chat_id: "-1001234567890"       # channel id OR group id OR user id
    parse_mode: MarkdownV2
    timeout_sec: 15
"""

from __future__ import annotations

import httpx

from sia.adapters.push.base import (
    PushAdapter,
    PushMessage,
    PushResult,
    push_registry,
    resolve_secret,
)
from sia.collector.url_validator import validate_source_url

_EMOJI = {"emergency": "🚨", "high": "⚠️", "normal": "📢", "info": "ℹ️"}


def _escape_mdv2(text: str) -> str:
    """Telegram MarkdownV2 reserved-char escape."""
    return "".join(
        "\\" + c if c in r"_*[]()~`>#+-=|{}.!" else c
        for c in text
    )


@push_registry.register("telegram")
class TelegramPusher(PushAdapter):
    async def _do(self, message: PushMessage) -> PushResult:
        token = resolve_secret(self.cfg.require("bot_token", str))
        chat_id = message.recipients[0] if message.recipients else self.cfg.require("chat_id")
        parse_mode = self.cfg.opt("parse_mode", "MarkdownV2")
        timeout = int(self.cfg.opt("timeout_sec", 15))

        if not token:
            return PushResult(channel="telegram", recipient=str(chat_id),
                              accepted=False, error="bot_token empty")

        api = f"https://api.telegram.org/bot{token}/sendMessage"
        validate_source_url(api, allowed_hosts={"api.telegram.org"})

        em = _EMOJI.get(message.level, "")
        if parse_mode == "MarkdownV2":
            title = _escape_mdv2(message.title)
            body = _escape_mdv2(message.body)
            url = _escape_mdv2(message.url or "")
            text = f"*{em} {title}*\n\n{body}" + (f"\n\n🔗 {url}" if url else "")
        else:
            text = f"{em} {message.title}\n\n{message.body}" \
                   + (f"\n\n🔗 {message.url}" if message.url else "")

        payload = {"chat_id": chat_id, "text": text[:4000],
                   "parse_mode": parse_mode, "disable_web_page_preview": False}
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(api, json=payload)
        body_j = resp.json() if resp.content else {}
        ok = resp.status_code == 200 and body_j.get("ok") is True
        return PushResult(
            channel="telegram",
            recipient=str(chat_id),
            accepted=ok,
            external_id=str(body_j.get("result", {}).get("message_id")) if ok else None,
            error=None if ok else f"HTTP {resp.status_code}: {body_j.get('description', resp.text)[:200]}",
        )
