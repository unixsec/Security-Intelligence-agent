"""Push channel adapters: email, wechat, wechat_work, feishu, telegram, dingtalk,
sms, **webhook**, **syslog**.

v0.4 added ``webhook`` (generic SIEM/SOAR HTTP POST with HMAC) and ``syslog``
(RFC 5424 over TCP+TLS / TCP / UDP).
"""

from sia.adapters.push.base import PushAdapter, PushMessage, push_registry

# Eager side-effect imports to populate the registry
from sia.adapters.push import (  # noqa: F401, E402
    dingtalk,
    email as _email,
    feishu,
    sms,
    syslog,
    telegram,
    wechat,
    wechat_work,
    webhook,
)

__all__ = ["PushAdapter", "PushMessage", "push_registry"]
