"""微信公众号 Template Message push (mp.weixin.qq.com).

Unlike WeChat Work, personal WeChat messaging requires an Official Account
with subscribed users. This adapter uses the Template Message API.

Config::
    kind: wechat
    app_id:     "secret:SIA_WECHAT_APPID"
    app_secret: "secret:SIA_WECHAT_APPSECRET"
    template_id: "TEMPLATE_ID_FROM_OA_ADMIN"
    # Recipients' openids are passed in PushMessage.recipients.
"""

from __future__ import annotations

import logging

import httpx

from sia.adapters.push.base import (
    PushAdapter,
    PushMessage,
    PushResult,
    push_registry,
    resolve_secret,
)
from sia.collector.url_validator import validate_source_url

logger = logging.getLogger(__name__)


@push_registry.register("wechat")
class WeChatOAPusher(PushAdapter):
    """微信公众号模板消息推送（需订阅关注）。"""

    # Simple in-process access_token cache. On multi-replica a Redis cache
    # would be shared — kept simple here; re-fetch is cheap.
    _token_cache: tuple[str, float] | None = None

    async def _fetch_access_token(self, appid: str, secret: str) -> str:
        import time
        now = time.time()
        if self._token_cache and self._token_cache[1] > now + 60:
            return self._token_cache[0]
        api = ("https://api.weixin.qq.com/cgi-bin/token"
               f"?grant_type=client_credential&appid={appid}&secret={secret}")
        validate_source_url(api, allowed_hosts={"api.weixin.qq.com"})
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(api)
            j = r.json()
        tok = j.get("access_token")
        if not tok:
            raise RuntimeError(f"wechat token fetch failed: {j}")
        self._token_cache = (tok, now + int(j.get("expires_in", 7000)))
        return tok

    async def _do(self, message: PushMessage) -> PushResult:
        appid = resolve_secret(self.cfg.require("app_id"))
        appsecret = resolve_secret(self.cfg.require("app_secret"))
        template_id = self.cfg.require("template_id")

        if not message.recipients:
            return PushResult(channel="wechat", recipient="(none)",
                              accepted=False, error="no openid recipients")

        try:
            token = await self._fetch_access_token(appid, appsecret)
        except Exception as e:
            return PushResult(channel="wechat", recipient="",
                              accepted=False, error=f"token: {e}")

        api = (f"https://api.weixin.qq.com/cgi-bin/message/template/send"
               f"?access_token={token}")
        sent = 0
        errs: list[str] = []
        async with httpx.AsyncClient(timeout=15) as client:
            for openid in message.recipients:
                payload = {
                    "touser": openid,
                    "template_id": template_id,
                    "url": message.url or "",
                    "data": {
                        "title": {"value": message.title},
                        "body": {"value": message.body[:200]},
                        "level": {"value": message.level.upper()},
                    },
                }
                r = await client.post(api, json=payload)
                j = r.json() if r.content else {}
                if r.status_code == 200 and j.get("errcode") == 0:
                    sent += 1
                else:
                    errs.append(f"{openid}: {j.get('errmsg') or r.status_code}")
        ok = sent == len(message.recipients)
        return PushResult(
            channel="wechat",
            recipient=f"{sent}/{len(message.recipients)} openid",
            accepted=ok,
            error=None if ok else " | ".join(errs)[:500],
        )
