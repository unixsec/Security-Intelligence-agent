"""Logging redaction filter (SEC-016).

Redacts common secret patterns from log messages BEFORE they leave the process.
Installed once from main.py on the root logger.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable

# Patterns we always scrub. Tuned to be broad; false positives are acceptable
# for logs since the real value is never needed after redaction.
_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # password=xxx, pwd=xxx, passwd=xxx (url or key=value form)
    (re.compile(r"(?i)(pass(?:word|wd)?)\s*[=:]\s*[^\s&'\"]+"), r"\1=***"),
    # secret=xxx, token=xxx, api[_-]?key=xxx
    (re.compile(r"(?i)\b(secret|token|api[_-]?key|access[_-]?key|authorization)\b"
                r"\s*[=:]\s*[^\s&'\"]+"), r"\1=***"),
    # mysql+aiomysql://user:PASSWORD@host/db — grab the password fragment
    (re.compile(r"(?i)(://[^:]+:)([^@]+)(@)"), r"\1***\3"),
    # Bearer eyJ... tokens
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9_\-\.]+"), "Bearer ***"),
    # -H "X-API-Key: xxxxx"
    (re.compile(r"(?i)(x-api-key[\"']?\s*[:=]\s*[\"']?)[^\s\"'&]+"), r"\1***"),
)


class RedactingFilter(logging.Filter):
    """Mutates LogRecord.msg (and args) to scrub secrets."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
            for pat, repl in _PATTERNS:
                msg = pat.sub(repl, msg)
            # Overwrite msg, clear args so formatter doesn't re-interpolate.
            record.msg = msg
            record.args = None
        except Exception:
            # Never let redaction failure kill logging.
            pass
        return True


_INSTALLED = False


def install_redaction(extra_logger_names: Iterable[str] = ()) -> None:
    """Attach the RedactingFilter to root + any extra named loggers (idempotent).

    Logging filters attached to a logger run only for records logged *on that
    logger directly* — they don't fire for propagated records. So we attach
    to the root logger PLUS known noisy loggers (sqlalchemy, httpx).
    """
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    f = RedactingFilter()
    targets = {"", "sqlalchemy.engine", "sqlalchemy.pool", "httpx", "urllib3"}
    targets.update(extra_logger_names)

    for name in targets:
        lg = logging.getLogger(name)
        # Avoid attaching twice if install_redaction is called by tests.
        if not any(isinstance(x, RedactingFilter) for x in lg.filters):
            lg.addFilter(f)
