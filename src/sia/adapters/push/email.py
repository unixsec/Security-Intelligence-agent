"""SMTP email push adapter (aiosmtplib).

Config::
    kind: email
    host: smtp.company.com
    port: 587
    use_starttls: true
    username: "secret:SIA_SMTP_USER"
    password: "secret:SIA_SMTP_PASSWORD"
    from_addr: "sia-alerts@company.com"
    timeout_sec: 30
"""

from __future__ import annotations

import logging
from email.message import EmailMessage

from sia.adapters.push.base import (
    PushAdapter,
    PushMessage,
    PushResult,
    push_registry,
    resolve_secret,
)

logger = logging.getLogger(__name__)


@push_registry.register("email")
class EmailPusher(PushAdapter):
    async def _do(self, message: PushMessage) -> PushResult:
        import aiosmtplib

        if not message.recipients:
            return PushResult(channel="email", recipient="(no recipients)",
                              accepted=False, error="no recipients")

        host = self.cfg.require("host")
        port = int(self.cfg.opt("port", 587))
        user = resolve_secret(self.cfg.opt("username", ""))
        pwd = resolve_secret(self.cfg.opt("password", ""))
        from_addr = self.cfg.require("from_addr")
        use_starttls = bool(self.cfg.opt("use_starttls", True))
        timeout = int(self.cfg.opt("timeout_sec", 30))

        email = EmailMessage()
        email["From"] = from_addr
        email["To"] = ", ".join(message.recipients)
        email["Subject"] = f"[SIA {message.level.upper()}] {message.title}"
        if message.html_body:
            email.set_content(message.body or "See HTML body.")
            email.add_alternative(message.html_body, subtype="html")
        else:
            email.set_content(message.body)
        for fname, blob, ctype in message.attachments:
            maintype, subtype = (ctype.split("/", 1) + ["octet-stream"])[:2]
            email.add_attachment(blob, maintype=maintype, subtype=subtype, filename=fname)

        try:
            await aiosmtplib.send(
                email, hostname=host, port=port,
                username=user or None, password=pwd or None,
                start_tls=use_starttls, timeout=timeout,
            )
            return PushResult(channel="email",
                              recipient=", ".join(message.recipients),
                              accepted=True)
        except Exception as e:  # noqa: BLE001
            logger.exception("email send failed")
            return PushResult(channel="email",
                              recipient=", ".join(message.recipients),
                              accepted=False, error=str(e))
