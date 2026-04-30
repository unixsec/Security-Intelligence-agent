"""Syslog (RFC 5424) push adapter for SIEM forwarding (v0.4-2).

Sends one structured-data line per event. Default protocol is **TCP+TLS**
(secure, reliable); UDP is supported but discouraged for cross-zone hops.

Config:

```yaml
- kind: syslog
  name: corp-siem
  host: siem.example.com
  port: 6514
  protocol: tcp_tls    # tcp_tls | tcp | udp
  facility: 16         # local0
  app_name: sia
  level_filter: ["emergency", "high", "normal"]
```

Message format (RFC 5424):

```
<PRI>1 TIMESTAMP HOSTNAME APP-NAME PROCID MSGID [sia@32473 level="..." title="..."] body
```

Note: receivers that only speak RFC 3164 (BSD syslog) will see the line as
plain text, which is acceptable — they get the title + body + level fields
in the SD section and can grep.
"""

from __future__ import annotations

import asyncio
import logging
import socket
import ssl
from datetime import datetime, timezone

from sia.adapters.push.base import (
    PushAdapter,
    PushMessage,
    PushResult,
    push_registry,
)

logger = logging.getLogger(__name__)

_LEVEL_TO_SEVERITY = {
    "emergency": 1,    # Alert
    "high": 2,         # Critical
    "normal": 5,       # Notice
    "info": 6,         # Informational
}


def _escape_sd_param(s: str) -> str:
    """Escape per RFC 5424 §6.3.3 — quotes, backslashes, ]."""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("]", "\\]")


def _format_5424(message: PushMessage, *, facility: int, app_name: str, hostname: str) -> bytes:
    severity = _LEVEL_TO_SEVERITY.get(message.level, 6)
    pri = facility * 8 + severity
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    sd = (
        f'[sia@32473 level="{_escape_sd_param(message.level)}" '
        f'title="{_escape_sd_param(message.title[:200])}" '
        f'tags="{_escape_sd_param(",".join(message.tags))}"]'
    )
    body = message.body.replace("\n", " ").strip()[:1024]
    line = f"<{pri}>1 {ts} {hostname} {app_name} - sia.intel {sd} {body}\n"
    return line.encode("utf-8")


@push_registry.register("syslog")
class SyslogPusher(PushAdapter):
    """RFC 5424 forwarder over TCP / TCP+TLS / UDP."""

    async def _do(self, message: PushMessage) -> PushResult:  # type: ignore[override]
        opts = self.config.options
        host = opts.get("host", "")
        port = int(opts.get("port", 514))
        proto = opts.get("protocol", "tcp_tls")
        facility = int(opts.get("facility", 16))
        app_name = opts.get("app_name", "sia")
        hostname = opts.get("hostname") or socket.gethostname()

        level_filter = opts.get("level_filter")
        if level_filter and message.level not in level_filter:
            return PushResult(
                channel="syslog", recipient=f"{host}:{port}",
                accepted=True, error=f"level {message.level} skipped (filter)",
            )

        if not host:
            return PushResult(channel="syslog", recipient="", accepted=False, error="missing host")

        line = _format_5424(message, facility=facility, app_name=app_name, hostname=hostname)

        try:
            if proto == "udp":
                # UDP "fire and forget" — acceptable for low-criticality forwarding.
                await asyncio.get_running_loop().run_in_executor(
                    None, _send_udp, host, port, line,
                )
                return PushResult(channel="syslog", recipient=f"{host}:{port}", accepted=True)

            ssl_ctx = ssl.create_default_context() if proto == "tcp_tls" else None
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host=host, port=port, ssl=ssl_ctx),
                timeout=10,
            )
            try:
                writer.write(line)
                await writer.drain()
            finally:
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass
            return PushResult(channel="syslog", recipient=f"{host}:{port}", accepted=True)

        except Exception as e:
            logger.exception("syslog delivery failed: %s:%s", host, port)
            return PushResult(channel="syslog", recipient=f"{host}:{port}", accepted=False, error=str(e))


def _send_udp(host: str, port: int, line: bytes) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.sendto(line, (host, port))
    finally:
        sock.close()
