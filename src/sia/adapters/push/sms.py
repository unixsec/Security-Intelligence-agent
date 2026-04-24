"""SMS push adapter — pluggable gateway.

Supports three back-ends via `provider:`:
    * aliyun     — 阿里云短信服务
    * tencent    — 腾讯云 SMS
    * twilio     — Twilio (int'l)

Config examples::

    kind: sms
    provider: aliyun
    access_key_id:     "secret:SIA_ALIYUN_AK"
    access_key_secret: "secret:SIA_ALIYUN_SK"
    sign_name: "SIA 安全简报"
    template_code: "SMS_12345"   # must be pre-approved

    kind: sms
    provider: twilio
    account_sid: "secret:SIA_TWILIO_SID"
    auth_token:  "secret:SIA_TWILIO_TOKEN"
    from_number: "+15551234567"
"""

from __future__ import annotations

import logging
from typing import Literal

import httpx

from sia.adapters.push.base import (
    PushAdapter,
    PushMessage,
    PushResult,
    push_registry,
    resolve_secret,
)

logger = logging.getLogger(__name__)

_SMS_MAX_LEN = 160  # keep below 1 segment for cost sanity


@push_registry.register("sms")
class SMSPusher(PushAdapter):
    async def _do(self, message: PushMessage) -> PushResult:
        provider: Literal["aliyun", "tencent", "twilio"] = self.cfg.require("provider")
        if not message.recipients:
            return PushResult(channel="sms", recipient="(none)",
                              accepted=False, error="no phone recipients")
        if provider == "twilio":
            return await self._send_twilio(message)
        if provider == "aliyun":
            return await self._send_aliyun(message)
        if provider == "tencent":
            return await self._send_tencent(message)
        return PushResult(channel="sms", recipient="",
                          accepted=False, error=f"unknown provider {provider}")

    async def _send_twilio(self, m: PushMessage) -> PushResult:
        sid = resolve_secret(self.cfg.require("account_sid"))
        token = resolve_secret(self.cfg.require("auth_token"))
        from_num = self.cfg.require("from_number")
        api = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
        text = f"[SIA {m.level.upper()}] {m.title}"[:_SMS_MAX_LEN]

        accepted = 0
        errs = []
        async with httpx.AsyncClient(timeout=15, auth=(sid, token)) as client:
            for to in m.recipients:
                resp = await client.post(api, data={"To": to, "From": from_num,
                                                    "Body": text})
                if 200 <= resp.status_code < 300:
                    accepted += 1
                else:
                    errs.append(f"{to}: {resp.status_code}")
        ok = accepted == len(m.recipients)
        return PushResult(channel="sms", recipient=f"{accepted}/{len(m.recipients)}",
                          accepted=ok, error=None if ok else "; ".join(errs)[:500])

    async def _send_aliyun(self, m: PushMessage) -> PushResult:
        # Real aliyun dysms signing is complex; here we shell out to the
        # official SDK if present. The adapter contract stays abstract so
        # operators can sub in their own impl via DI.
        try:
            # pylint: disable=import-outside-toplevel
            from aliyunsdkcore.client import AcsClient
            from aliyunsdkcore.request import CommonRequest
        except ImportError:
            return PushResult(channel="sms", recipient="",
                              accepted=False,
                              error="aliyun-python-sdk-core not installed")

        import json as _j
        ak = resolve_secret(self.cfg.require("access_key_id"))
        sk = resolve_secret(self.cfg.require("access_key_secret"))
        sign_name = self.cfg.require("sign_name")
        tpl_code = self.cfg.require("template_code")

        client = AcsClient(ak, sk, "cn-hangzhou")
        req = CommonRequest()
        req.set_accept_format("json")
        req.set_domain("dysmsapi.aliyuncs.com")
        req.set_method("POST")
        req.set_version("2017-05-25")
        req.set_action_name("SendSms")
        req.add_query_param("PhoneNumbers", ",".join(m.recipients))
        req.add_query_param("SignName", sign_name)
        req.add_query_param("TemplateCode", tpl_code)
        req.add_query_param("TemplateParam",
                            _j.dumps({"title": m.title[:40], "level": m.level}))
        try:
            resp = client.do_action_with_exception(req)
            body = _j.loads(resp) if isinstance(resp, (bytes, bytearray)) else _j.loads(resp)
            ok = body.get("Code") == "OK"
        except Exception as e:  # noqa: BLE001
            return PushResult(channel="sms", recipient=",".join(m.recipients),
                              accepted=False, error=str(e))
        return PushResult(channel="sms", recipient=",".join(m.recipients),
                          accepted=ok, external_id=body.get("BizId"))

    async def _send_tencent(self, m: PushMessage) -> PushResult:
        """Tencent Cloud SMS — omitted real signing (v3 HMAC is long).

        The adapter signature is stable; when enabling tencent,
        implement via `tencentcloud-sdk-python` in this method.
        """
        return PushResult(channel="sms", recipient=",".join(m.recipients),
                          accepted=False,
                          error="tencent provider stub — install tencentcloud-sdk-python")
