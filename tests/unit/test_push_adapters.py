"""Smoke tests for each PushAdapter — HTTP mocked, no real sends."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from sia.adapters.push.base import PushMessage
from sia.adapters.push import push_registry


def _fake_response(status=200, json_body=None):
    r = type("R", (), {})()
    r.status_code = status
    r.content = b'{"ok":true}'
    r.text = '{"ok":true}'
    r.json = lambda: json_body or {"ok": True}
    return r


@pytest.mark.asyncio
async def test_wechat_work_webhook_sent(monkeypatch):
    adapter = push_registry.build("wechat_work",
                                   {"webhook": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=fake"})
    with patch("httpx.AsyncClient") as client_cls:
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.post = AsyncMock(return_value=_fake_response(json_body={"errcode": 0, "msgid": "m1"}))
        client_cls.return_value = client
        with patch("sia.adapters.push.wechat_work.validate_source_url"):
            result = await adapter.run(PushMessage(title="t", body="b"))
    assert result.accepted is True
    assert result.external_id == "m1"


@pytest.mark.asyncio
async def test_feishu_with_signing(monkeypatch):
    adapter = push_registry.build("feishu", {
        "webhook": "https://open.feishu.cn/open-apis/bot/v2/hook/fake",
        "signing_secret": "s3cr3t",
    })
    with patch("httpx.AsyncClient") as client_cls:
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.post = AsyncMock(return_value=_fake_response(json_body={"code": 0}))
        client_cls.return_value = client
        with patch("sia.adapters.push.feishu.validate_source_url"):
            result = await adapter.run(PushMessage(title="t", body="b", level="emergency"))
    assert result.accepted is True
    # Body should have been a signed card
    call = client.post.call_args
    payload = call.kwargs["json"]
    assert "timestamp" in payload
    assert "sign" in payload


@pytest.mark.asyncio
async def test_dingtalk_sign(monkeypatch):
    adapter = push_registry.build("dingtalk", {
        "webhook": "https://oapi.dingtalk.com/robot/send?access_token=fake",
        "secret": "SEC00001",
    })
    with patch("httpx.AsyncClient") as client_cls:
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.post = AsyncMock(return_value=_fake_response(json_body={"errcode": 0}))
        client_cls.return_value = client
        with patch("sia.adapters.push.dingtalk.validate_source_url"):
            result = await adapter.run(PushMessage(title="t", body="b"))
    # Signed URL should have appended timestamp and sign query params
    called_url = client.post.call_args.args[0]
    assert "timestamp=" in called_url and "sign=" in called_url
    assert result.accepted is True


@pytest.mark.asyncio
async def test_telegram_markdownv2_escape(monkeypatch):
    adapter = push_registry.build("telegram", {
        "bot_token": "1234:fake",
        "chat_id": "-100999",
    })
    with patch("httpx.AsyncClient") as client_cls:
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.post = AsyncMock(return_value=_fake_response(
            json_body={"ok": True, "result": {"message_id": 42}}
        ))
        client_cls.return_value = client
        with patch("sia.adapters.push.telegram.validate_source_url"):
            result = await adapter.run(PushMessage(
                title="Hi *star* _under_",  # reserved MDv2 chars
                body="danger: . ! -",
            ))
    assert result.accepted is True
    sent_text = client.post.call_args.kwargs["json"]["text"]
    # All reserved chars are backslash-escaped
    assert r"\*star\*" in sent_text
    assert r"\_under\_" in sent_text
    assert r"\." in sent_text


@pytest.mark.asyncio
async def test_dispatch_tlp_filtering():
    from sia.reporter.pusher.dispatcher import (
        Subscriber, _should_deliver,
    )
    from sia.adapters.push.base import PushMessage
    msg = PushMessage(title="t", body="b", level="high")

    sub_green = Subscriber(id=1, name="a", preferred_channel="email",
                           max_tlp="GREEN")
    # msg tlp=AMBER, sub max=GREEN → blocked
    assert _should_deliver(sub_green, msg, message_tlp="AMBER") is False
    # msg tlp=GREEN, sub max=GREEN → allowed
    assert _should_deliver(sub_green, msg, message_tlp="GREEN") is True


@pytest.mark.asyncio
async def test_dispatch_subscribe_level_filter():
    from sia.reporter.pusher.dispatcher import Subscriber, _should_deliver
    from sia.adapters.push.base import PushMessage

    sub = Subscriber(id=2, name="b", preferred_channel="feishu",
                     max_tlp="RED", subscribe_level="p0_p1_only")
    # 'normal' level message → blocked
    assert _should_deliver(sub, PushMessage(title="t", body="b", level="normal")) is False
    # 'high' → allowed
    assert _should_deliver(sub, PushMessage(title="t", body="b", level="high")) is True
    # 'emergency' → allowed
    assert _should_deliver(sub, PushMessage(title="t", body="b", level="emergency")) is True


@pytest.mark.asyncio
async def test_email_requires_recipients():
    adapter = push_registry.build("email", {
        "host": "smtp.example.com",
        "from_addr": "x@example.com",
    })
    result = await adapter.run(PushMessage(title="t", body="b"))
    assert result.accepted is False
    assert "recipient" in result.error.lower() or "no recipients" in result.error.lower()
