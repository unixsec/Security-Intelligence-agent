"""Push channel adapters: email, wechat, wechat_work, feishu, telegram, dingtalk, sms."""

from sia.adapters.push.base import PushAdapter, PushMessage, push_registry

# Eager side-effect imports to populate the registry
from sia.adapters.push import (  # noqa: F401, E402
    dingtalk,
    email as _email,
    feishu,
    sms,
    telegram,
    wechat,
    wechat_work,
)

__all__ = ["PushAdapter", "PushMessage", "push_registry"]
