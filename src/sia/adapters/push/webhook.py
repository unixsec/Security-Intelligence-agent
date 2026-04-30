"""Generic SIEM / SOAR webhook adapter (v0.4-2).

Use this for any HTTP POST sink (Splunk HEC, Elastic, generic SOAR ingest,
custom internal pipelines, ServiceNow eventing). Two security primitives:

* **HMAC signature** — when ``secret`` is set, every request carries
  ``X-SIA-Signature: sha256=<hex>`` over the **raw JSON body**. Receivers
  verify with the shared secret. Replay protection is the receiver's job
  (we ship a ``X-SIA-Timestamp`` they can window).
* **SSRF guard** — the configured URL is validated through the same
  ``url_validator`` used for collectors, so a misconfigured webhook
  pointing at ``169.254.169.254`` or an internal-only host is refused.

Config (per push channel in ``config/push_channels.yaml``):

```yaml
- kind: webhook
  name: splunk-hec
  url: https://splunk.example.com/services/collector/event
  secret: secret:SPLUNK_HEC_TOKEN          # HMAC key
  headers:
    Authorization: "Splunk ${SPLUNK_HEC_TOKEN}"
  timeout_seconds: 10
  level_filter: ["emergency", "high"]      # optional; default all
```

Payload shape (stable; documented in ``API_REFERENCE.md`` after v0.4):

```json
{
  "event": "sia.intel",
  "level": "emergency",
  "title": "...",
  "body": "...",
  "url": "https://sia.example.com/intelligence/123",
  "tags": ["P0", "kev"],
  "sent_at": "2026-04-28T10:23:00Z"
}
```
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time

import httpx

from sia.adapters.push.base import (
    PushAdapter,
    PushMessage,
    PushResult,
    push_registry,
    resolve_secret,
)
from sia.collector.url_validator import UnsafeURLError, validate_source_url

logger = logging.getLogger(__name__)


@push_registry.register("webhook")
class WebhookPusher(PushAdapter):
    """POST a JSON payload to an arbitrary HTTPS endpoint with HMAC signing."""

    async def _do(self, message: PushMessage) -> PushResult:  # type: ignore[override]
        url: str = self.config.options.get("url", "")
        if not url:
            return PushResult(channel="webhook", recipient="", accepted=False, error="missing url")

        # SSRF guard: same validator we use for collectors.
        try:
            validate_source_url(url)
        except UnsafeURLError as e:
            return PushResult(channel="webhook", recipient=url, accepted=False, error=f"unsafe url: {e}")

        level_filter = self.config.options.get("level_filter")
        if level_filter and message.level not in level_filter:
            return PushResult(
                channel="webhook", recipient=url, accepted=True,
                external_id=None, error=f"level {message.level} skipped (filter={level_filter})",
            )

        secret = resolve_secret(self.config.options.get("secret", "") or "")
        timeout = float(self.config.options.get("timeout_seconds", 10))

        payload = {
            "event": "sia.intel",
            "level": message.level,
            "title": message.title,
            "body": message.body,
            "url": message.url,
            "tags": message.tags,
            "sent_at": message.sent_at.isoformat() + "Z",
        }
        body_bytes = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

        headers: dict[str, str] = {"Content-Type": "application/json"}
        # Operator-supplied static headers (e.g. Splunk Authorization)
        for k, v in (self.config.options.get("headers") or {}).items():
            headers[str(k)] = resolve_secret(str(v))

        ts = str(int(time.time()))
        headers["X-SIA-Timestamp"] = ts
        if secret:
            mac = hmac.new(secret.encode(), ts.encode() + b"." + body_bytes, hashlib.sha256).hexdigest()
            headers["X-SIA-Signature"] = f"sha256={mac}"

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, content=body_bytes, headers=headers)
            ok = 200 <= resp.status_code < 300
            return PushResult(
                channel="webhook",
                recipient=url,
                accepted=ok,
                external_id=resp.headers.get("x-request-id") or resp.headers.get("x-correlation-id"),
                error=None if ok else f"HTTP {resp.status_code}: {resp.text[:200]}",
            )
        except Exception as e:  # network errors land here
            logger.exception("webhook delivery failed: %s", url)
            return PushResult(channel="webhook", recipient=url, accepted=False, error=str(e))
