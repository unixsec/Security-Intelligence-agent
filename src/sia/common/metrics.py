"""Prometheus metrics — single registry shared across the API and consumer.

OBS-1: HPA / alerting / SLO measurement need business-level signals, not
just CPU+memory. This module declares the small set we instrument; new
metrics should be added here so labels stay consistent.

Conventions
-----------
- Names are ``sia_<subsystem>_<unit>`` (Prometheus best practice).
- ``Counter`` is for monotonically-increasing events (use ``_total`` suffix).
- ``Histogram`` is for distributions (latency, size). Default buckets are
  fine for sub-second LLM latencies; tune in production after seeing data.
- ``Gauge`` is for last-value snapshots (lag, open circuits).
- We avoid high-cardinality labels: model + provider yes, intel-id no.

Wire-up
-------
``main.create_app`` mounts ``make_asgi_app()`` at ``/metrics``. The path is
already excluded from rate-limiting (see ``RateLimitMiddleware._HEALTH_PATHS``
extension below) and from auth (FastAPI doesn't apply Depends to mounted
sub-apps anyway).
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# ─── Collector ────────────────────────────────────────────────────────────
intel_collected_total = Counter(
    "sia_intel_collected_total",
    "Number of intel items returned by collectors.",
    ["source", "result"],   # result: success | parse_error | http_error | unsafe_url
)

# ─── Analyzer ─────────────────────────────────────────────────────────────
intel_analyzed_total = Counter(
    "sia_intel_analyzed_total",
    "Number of intel items completing the analyze pipeline.",
    ["priority", "category"],
)

intel_dlq_total = Counter(
    "sia_intel_dlq_total",
    "Number of intel messages routed to the dead-letter stream.",
    ["reason"],
)

# ─── LLM Gateway ──────────────────────────────────────────────────────────
llm_call_duration_seconds = Histogram(
    "sia_llm_call_duration_seconds",
    "LLM call wall-clock duration.",
    ["provider", "model", "prompt"],
)

llm_call_total = Counter(
    "sia_llm_call_total",
    "LLM calls grouped by outcome.",
    ["provider", "model", "result"],   # result: success | error | circuit_open
)

llm_tokens_total = Counter(
    "sia_llm_tokens_total",
    "LLM token usage (input + output, summed).",
    ["provider", "model", "kind"],     # kind: input | output
)

# ─── Resilience ───────────────────────────────────────────────────────────
circuit_state = Gauge(
    "sia_circuit_state",
    "Per-circuit state. 0=closed, 1=half_open, 2=open.",
    ["name"],
)

# ─── Streams ──────────────────────────────────────────────────────────────
stream_lag = Gauge(
    "sia_stream_lag",
    "Pending message count for the named Redis Stream consumer group.",
    ["stream", "group"],
)

# ─── Reporter / Push ──────────────────────────────────────────────────────
reports_generated_total = Counter(
    "sia_reports_generated_total",
    "Reports persisted by the reporter pipeline.",
    ["report_type"],
)

push_dispatch_total = Counter(
    "sia_push_dispatch_total",
    "Push dispatcher attempts grouped by outcome.",
    ["channel", "result"],   # result: ok | retry | failed
)


__all__ = [
    "intel_collected_total",
    "intel_analyzed_total",
    "intel_dlq_total",
    "llm_call_duration_seconds",
    "llm_call_total",
    "llm_tokens_total",
    "circuit_state",
    "stream_lag",
    "reports_generated_total",
    "push_dispatch_total",
]
