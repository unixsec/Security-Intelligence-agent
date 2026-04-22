"""Data anonymizer — sanitize sensitive data before sending to cloud LLMs.

Three-layer defense:
1. Regex-based pattern matching (IPs, hostnames, employee names)
2. Configurable from llm_gateway.yaml
3. Reversible mapping for de-anonymization of responses
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class AnonymizationContext:
    """Per-request anonymization state — thread-safe by design."""

    mapping: dict[str, str] = field(default_factory=dict)    # placeholder → original
    reverse: dict[str, str] = field(default_factory=dict)    # original → placeholder

    def deanonymize(self, text: str) -> str:
        """Restore anonymized placeholders in LLM response to originals."""
        result = text
        for placeholder, original in self.mapping.items():
            result = result.replace(placeholder, original)
        return result


class DataAnonymizer:
    """Anonymize sensitive data in messages before cloud LLM calls.

    Thread-safe: each call to anonymize_messages() returns an independent
    AnonymizationContext that callers must pass back to deanonymize().
    """

    def __init__(self, config: dict | None = None) -> None:
        self._patterns: list[dict] = []

        if config and config.get("enabled", False):
            self._patterns = config.get("patterns", [])
            # Pre-compile regexes for performance
            self._compiled: list[tuple[re.Pattern, str]] = []
            for p in self._patterns:
                regex = p.get("regex", "")
                replacement = p.get("replacement", "[REDACTED]")
                if regex:
                    try:
                        self._compiled.append((re.compile(regex), replacement))
                    except re.error:
                        logger.warning("Invalid anonymization regex (skipped): %s", regex)
            logger.info("Anonymizer initialized with %d patterns", len(self._compiled))

    def anonymize_messages(
        self, messages: list[dict[str, str]]
    ) -> tuple[list[dict[str, str]], AnonymizationContext]:
        """Anonymize all messages.

        Returns (sanitized_messages, context) — pass context to deanonymize_text().
        """
        anon_ctx = AnonymizationContext()
        result = [
            {**msg, "content": self._anonymize_text(msg.get("content", ""), anon_ctx)}
            for msg in messages
        ]
        return result, anon_ctx

    @staticmethod
    def deanonymize_text(text: str, anon_ctx: AnonymizationContext) -> str:
        """Restore anonymized placeholders using the per-request context."""
        return anon_ctx.deanonymize(text)

    def _anonymize_text(self, text: str, ctx: AnonymizationContext) -> str:
        """Apply all anonymization patterns to text.

        Collects every non-overlapping match across all patterns first, then
        substitutes in a single pass. This avoids two latent bugs:
          - later patterns matching characters *inside* placeholders emitted
            by earlier patterns (which would corrupt the redaction)
          - re-running the full substitution map on every pattern iteration
        """
        if not self._compiled:
            return text

        # Gather candidate spans from every pattern; later we filter overlaps.
        candidates: list[tuple[int, int, str, str]] = []  # (start, end, original, template)
        for compiled_re, replacement_template in self._compiled:
            for match in compiled_re.finditer(text):
                candidates.append(
                    (match.start(), match.end(), match.group(0), replacement_template)
                )

        if not candidates:
            return text

        # Sort by start, then prefer the longest match on ties so we redact
        # the broadest sensitive span rather than a shorter suffix/prefix.
        candidates.sort(key=lambda c: (c[0], -(c[1] - c[0])))

        chunks: list[str] = []
        cursor = 0
        for start, end, original, template in candidates:
            if start < cursor:
                # Overlaps a previously accepted match — skip.
                continue
            if cursor < start:
                chunks.append(text[cursor:start])

            placeholder = ctx.reverse.get(original)
            if placeholder is None:
                short_id = uuid.uuid4().hex[:6]
                placeholder = f"{template.rstrip(']')}_{short_id}]"
                ctx.mapping[placeholder] = original
                ctx.reverse[original] = placeholder

            chunks.append(placeholder)
            cursor = end

        if cursor < len(text):
            chunks.append(text[cursor:])
        return "".join(chunks)

    @property
    def has_patterns(self) -> bool:
        return bool(getattr(self, "_compiled", []))
