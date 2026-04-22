"""Push notification channels: WeChat Work, Feishu, Email."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class BasePushChannel(ABC):
    """Base class for all push notification channels."""

    @abstractmethod
    async def send(self, recipient: dict, content: dict) -> bool:
        """Send a notification. Returns True on success."""
        ...


class WeChatWorkChannel(BasePushChannel):
    """WeChat Work (企业微信) webhook push."""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    async def send(self, recipient: dict, content: dict) -> bool:
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": self._format_markdown(content),
            },
        }
        if mentioned_list := recipient.get("mentioned_list"):
            payload["markdown"]["mentioned_list"] = mentioned_list

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(self.webhook_url, json=payload)
                resp.raise_for_status()
                result = resp.json()
                if result.get("errcode") != 0:
                    logger.error("WeChat Work push failed: %s", result.get("errmsg"))
                    return False
            return True
        except Exception:
            logger.exception("WeChat Work push error")
            return False

    @staticmethod
    def _format_markdown(content: dict) -> str:
        title = content.get("title", "Security Intelligence Alert")
        body = content.get("body", "")
        priority = content.get("priority", "")
        color = {"P0": "warning", "P1": "info"}.get(priority, "comment")
        return f"## <font color=\"{color}\">[{priority}]</font> {title}\n\n{body}"


class FeishuChannel(BasePushChannel):
    """Feishu (飞书) webhook push."""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    async def send(self, recipient: dict, content: dict) -> bool:
        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": content.get("title", "Alert")},
                    "template": "red" if content.get("priority") == "P0" else "blue",
                },
                "elements": [
                    {
                        "tag": "markdown",
                        "content": content.get("body", ""),
                    }
                ],
            },
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(self.webhook_url, json=payload)
                resp.raise_for_status()
            return True
        except Exception:
            logger.exception("Feishu push error")
            return False


class EmailChannel(BasePushChannel):
    """Email notification via SMTP."""

    def __init__(self, smtp_config: dict):
        self.config = smtp_config

    async def send(self, recipient: dict, content: dict) -> bool:
        import aiosmtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        to_addr = recipient.get("email")
        if not to_addr:
            return False

        msg = MIMEMultipart("alternative")
        msg["Subject"] = content.get("title", "SIA Alert")
        msg["From"] = self.config.get("from_addr", "sia@company.com")
        msg["To"] = to_addr

        html_body = content.get("html_body", content.get("body", ""))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        try:
            await aiosmtplib.send(
                msg,
                hostname=self.config.get("host", "localhost"),
                port=self.config.get("port", 587),
                username=self.config.get("username"),
                password=self.config.get("password"),
                use_tls=self.config.get("use_tls", True),
            )
            return True
        except Exception:
            logger.exception("Email push error")
            return False


CHANNEL_REGISTRY: dict[str, type[BasePushChannel]] = {
    "wechat_work": WeChatWorkChannel,
    "feishu": FeishuChannel,
    "email": EmailChannel,
}
