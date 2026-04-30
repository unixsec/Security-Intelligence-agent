"""Intelligence analysis pipeline — orchestrates the full analysis workflow."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any

from sqlalchemy import select, update


def _strip_html(text: str | None) -> str:
    """Strip HTML tags and collapse whitespace."""
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", clean).strip()

from sia.common.database import get_db_context
from sia.common.redis import (
    STREAM_ANALYZED,
    STREAM_EMERGENCY,
    STREAM_RAW_INTEL,
    get_redis,
    publish_to_stream,
)
from sia.models.intelligence import Intelligence
from sia.models.system import IocIndicator, LLMCallLog

logger = logging.getLogger(__name__)


async def persist_analysis_result(
    *,
    ctx: Any,
    intel_id: int,
    classification: dict,
    scores: dict,
    iocs: dict,
    analysis: dict,
) -> dict:
    """Persist all analysis results to database.

    Called as the final step of the analyze_intel workflow.
    """
    from sia.analyzer.scorer import compute_total_score, determine_priority, apply_overrides

    async with get_db_context() as session:
        # Compute total score and priority
        dimension_scores = {
            "relevance": scores.get("relevance", 5.0),
            "severity": scores.get("severity", 5.0),
            "timeliness": scores.get("timeliness", 5.0),
            "actionability": scores.get("actionability", 5.0),
            "quality": scores.get("quality", 5.0),
        }
        total = compute_total_score(dimension_scores)
        priority = determine_priority(total)

        # Get intel record for override checks
        stmt = select(Intelligence).where(Intelligence.id == intel_id)
        result = await session.execute(stmt)
        intel = result.scalar_one_or_none()
        if not intel:
            logger.error("Intelligence record not found: %d", intel_id)
            return {"error": "not_found"}

        # Apply rule-based overrides
        override_data = {
            "is_kev": intel.is_kev,
            "cvss_score": float(intel.cvss_score) if intel.cvss_score else None,
            "category": classification.get("primary_category"),
            "asset_match": ctx.get("asset_match", False) if ctx else False,
        }
        final_priority = await apply_overrides(session, override_data, priority)

        # Update intelligence record
        impact = analysis.get("impact_assessment", {})
        actions = analysis.get("recommended_actions", [])

        await session.execute(
            update(Intelligence)
            .where(Intelligence.id == intel_id)
            .values(
                primary_category=classification.get("primary_category"),
                secondary_category=classification.get("secondary_category"),
                tags=classification.get("tags"),
                tlp_level=classification.get("tlp_level", "GREEN"),
                # FN-6: bilingual fields — both must be present in v1.2
                # classify_intel output. Fall back gracefully if a (legacy)
                # provider replied without them.
                title_zh=classification.get("title_zh"),
                summary=classification.get("summary_en"),
                summary_zh=classification.get("summary_zh"),
                score_relevance=dimension_scores["relevance"],
                score_severity=dimension_scores["severity"],
                score_timeliness=dimension_scores["timeliness"],
                score_actionability=dimension_scores["actionability"],
                score_quality=dimension_scores["quality"],
                total_score=total,
                priority_level=final_priority,
                llm_comment=impact.get("description"),
                llm_impact=json.dumps(impact, ensure_ascii=False) if impact else None,
                llm_action=json.dumps(actions, ensure_ascii=False) if actions else None,
                llm_model_used=ctx.get("_llm_meta_classify_intel", {}).get("model", "unknown") if ctx else "unknown",
                mitre_tactics=analysis.get("mitre_attack", {}).get("tactics"),
                mitre_techniques=analysis.get("mitre_attack", {}).get("techniques"),
                processing_status="analyzed",
                analyzed_at=datetime.now(),
            )
        )

        # Persist IOCs
        indicators = iocs.get("indicators", [])
        for ioc in indicators:
            session.add(IocIndicator(
                intel_id=intel_id,
                ioc_type=ioc.get("type", "unknown"),
                ioc_value=ioc.get("value", ""),
                context=ioc.get("context"),
                confidence=ioc.get("confidence", "medium"),
            ))

        # Log LLM calls
        for prompt_name in ["classify_intel", "score_intel", "extract_ioc", "analyze_intel"]:
            meta = ctx.get(f"_llm_meta_{prompt_name}") if ctx else None
            if meta:
                total_tokens = meta.get("total_tokens", meta.get("tokens", 0))
                # Provider reports split counts; fall back to an even split only
                # if the provider genuinely did not return the breakdown.
                input_tokens = meta.get("input_tokens")
                output_tokens = meta.get("output_tokens")
                if input_tokens is None or output_tokens is None:
                    input_tokens = total_tokens // 2
                    output_tokens = total_tokens - input_tokens
                session.add(LLMCallLog(
                    model_name=meta.get("model", "unknown"),
                    provider_type=meta.get("provider", "unknown"),
                    prompt_template=prompt_name,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    latency_ms=meta.get("latency_ms", 0),
                    status="success",
                    intel_id=intel_id,
                    trace_id=ctx.trace_id if hasattr(ctx, "trace_id") else None,
                ))

        # Capture values before session closes (avoid detached instance access)
        intel_title = intel.title

    # OBS-1: publish per-priority/category metric for HPA & SLO purposes.
    try:
        from sia.common.metrics import intel_analyzed_total
        intel_analyzed_total.labels(
            priority=final_priority,
            category=classification.get("primary_category", "uncategorized"),
        ).inc()
    except Exception:
        logger.debug("metrics increment failed", exc_info=True)

    # v0.4-1: Milvus indexing + level 2/3 dedup. Best-effort; never blocks
    # the analyzer. If a same-day or cross-day match is found we log it so
    # the analyst UI can fold related items (UI rendering is v0.4+).
    try:
        from sia.analyzer.dedup import (
            check_cross_day_dedup,
            check_vector_similarity,
            index_intel_vector,
        )
        from sia.common.milvus_client import is_enabled as _milvus_on

        if _milvus_on():
            cat = classification.get("primary_category") or "uncategorized"
            same_day = await check_vector_similarity(
                title=intel_title,
                content="",            # title alone is enough at this point; full content already stored
                exclude_intel_id=intel_id,
            )
            cross_day = await check_cross_day_dedup(
                title=intel_title,
                content="",
                exclude_intel_id=intel_id,
            ) if not same_day else []

            if same_day:
                logger.info(
                    "Level-2 dedup hit: intel_id=%d related_to=%s sim=%.3f",
                    intel_id, same_day[0]["intel_id"], same_day[0]["similarity"],
                )
            elif cross_day:
                logger.info(
                    "Level-3 dedup hit: intel_id=%d resurfacing_of=%s sim=%.3f",
                    intel_id, cross_day[0]["intel_id"], cross_day[0]["similarity"],
                )

            # Always index the new vector after the related-to lookup so the
            # next item can match against it.
            await index_intel_vector(
                intel_id=intel_id,
                title=intel_title,
                content="",
                category=cat,
                collected_at=datetime.now(),
            )
    except Exception:
        logger.exception("vector dedup pass failed (non-fatal); continuing")

    # Publish to analyzed stream (outside DB session)
    await publish_to_stream(STREAM_ANALYZED, {
        "intel_id": str(intel_id),
        "priority": final_priority,
        "total_score": str(total),
        "category": classification.get("primary_category", ""),
    })

    # Emergency stream for P0
    if final_priority == "P0":
        await publish_to_stream(STREAM_EMERGENCY, {
            "intel_id": str(intel_id),
            "title": intel_title,
            "priority": "P0",
            "total_score": str(total),
        })
        logger.warning("P0 intelligence detected: id=%d title=%s", intel_id, intel_title)

    return {
        "intel_id": intel_id,
        "priority": final_priority,
        "total_score": total,
        "ioc_count": len(indicators),
    }


async def run_analysis_consumer() -> None:
    """Consumer loop: reads from raw_intel_stream and triggers analysis workflows.

    SEC-018 — Graceful shutdown: on SIGTERM / SIGINT we set a stop flag, finish
    the current message, then exit. The K8s terminationGracePeriodSeconds
    should match the longest expected analysis duration.
    """
    import asyncio
    import signal

    from sia.gateway.llm.gateway import LLMGateway
    from sia.gateway.llm.prompt_manager import PromptManager
    from sia.gateway.workflow.engine import StepRegistry, WorkflowContext, WorkflowEngine
    from sia.gateway.workflow.steps.llm_call import LLMCallStepExecutor
    from sia.gateway.workflow.steps.python_func import PythonFuncStepExecutor
    from sia.config import get_llm_config, get_settings

    settings = get_settings()

    # OBS-2: consumer process is a separate Python entry point from the
    # FastAPI app, so it needs its own tracer init. No-op when not configured.
    try:
        from sia.common.tracing import init_tracing
        init_tracing(service_name="sia-consumer")
    except Exception:
        logger.exception("consumer tracing init failed; continuing")

    llm_config = get_llm_config()
    gateway = LLMGateway(llm_config)
    prompt_mgr = PromptManager(settings.prompts_dir)

    registry = StepRegistry()
    registry.register("llm_call", LLMCallStepExecutor(gateway, prompt_mgr))
    registry.register("python_func", PythonFuncStepExecutor())

    engine = WorkflowEngine(registry)
    engine.load_all(settings.workflows_dir)

    redis = get_redis()
    consumer_name = "analyzer-1"
    group = "analyzer-group"

    stop_event = asyncio.Event()

    # Start outbox publisher as a sibling task. It drains pending outbox rows
    # into Redis Streams so business writes that used `enqueue_outbox` are
    # atomically committed AND reliably delivered (ARCHITECTURE_REVIEW §B-5).
    from sia.common.outbox import run_outbox_publisher
    outbox_task = asyncio.create_task(
        run_outbox_publisher(stop_event=stop_event),
        name="outbox_publisher",
    )

    def _request_stop(signum: int, _frame) -> None:
        logger.info("Consumer received signal %d — draining current batch", signum)
        stop_event.set()

    try:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, stop_event.set)
            except NotImplementedError:
                # Windows — fall back to synchronous signal handler
                signal.signal(sig, _request_stop)
    except Exception:
        logger.exception("Failed to install signal handlers (continuing without graceful shutdown)")

    logger.info("Analysis consumer started: consumer=%s group=%s", consumer_name, group)

    # FN-5: exponential backoff on outer-loop failure (the inner per-message
    # try/except already DLQs poison messages, so the outer except only fires
    # on Redis or unexpected systemic errors).
    from sia.common.retry import exponential_backoff
    consec_outer_failures = 0

    while not stop_event.is_set():
        try:
            messages = await redis.xreadgroup(
                group, consumer_name,
                {STREAM_RAW_INTEL: ">"},
                count=5,
                block=5000,
            )
            consec_outer_failures = 0  # successful read resets backoff
            if not messages:
                continue

            for stream_name, entries in messages:
                for msg_id, data in entries:
                    try:
                        intel_id = int(data.get("intel_id", 0))
                        if not intel_id:
                            await redis.xack(STREAM_RAW_INTEL, group, msg_id)
                            continue

                        # Load intel from DB — capture all values inside session
                        intel_data: dict | None = None
                        async with get_db_context() as session:
                            stmt = select(Intelligence).where(Intelligence.id == intel_id)
                            result = await session.execute(stmt)
                            intel = result.scalar_one_or_none()
                            if intel:
                                intel_data = {
                                    "intel_id": intel.id,
                                    "title": _strip_html(intel.title),
                                    "content": _strip_html(intel.content),
                                    "source_name": intel.source_name or "",
                                    "published_at": str(intel.published_at),
                                    "cve_id": intel.cve_id,
                                    "cvss_score": str(intel.cvss_score) if intel.cvss_score else None,
                                    "epss_score": str(intel.epss_score) if intel.epss_score else None,
                                    "is_kev": intel.is_kev,
                                    "affected_products": intel.affected_products,
                                    "asset_match": False,
                                }

                        if not intel_data:
                            logger.warning("Intel not found for analysis: %d", intel_id)
                            await redis.xack(STREAM_RAW_INTEL, group, msg_id)
                            continue

                        # Build workflow context
                        ctx = WorkflowContext(workflow_id="analyze_intel")
                        ctx.set("input", intel_data)

                        await engine.execute("analyze_intel", ctx)
                        await redis.xack(STREAM_RAW_INTEL, group, msg_id)
                        logger.info("Analysis completed for intel_id=%d", intel_id)

                    except Exception:
                        logger.exception("Failed to process message %s", msg_id)
                        # ACK the message and move to DLQ to prevent poison message loops
                        try:
                            from sia.common.redis import STREAM_DLQ
                            await publish_to_stream(STREAM_DLQ, {
                                "original_stream": STREAM_RAW_INTEL,
                                "original_msg_id": str(msg_id),
                                "intel_id": data.get("intel_id", ""),
                                "error": "analysis_failed",
                            })
                            try:
                                from sia.common.metrics import intel_dlq_total
                                intel_dlq_total.labels(reason="analysis_failed").inc()
                            except Exception:
                                pass
                            await redis.xack(STREAM_RAW_INTEL, group, msg_id)
                        except Exception:
                            logger.exception("Failed to move message %s to DLQ", msg_id)

        except Exception:
            logger.exception("Analysis consumer outer loop error (attempt=%d)", consec_outer_failures)
            await exponential_backoff(consec_outer_failures, base=1.0, cap=60.0)
            consec_outer_failures += 1

    # Drain the outbox publisher too before exiting.
    try:
        await asyncio.wait_for(outbox_task, timeout=10)
    except asyncio.TimeoutError:
        logger.warning("outbox publisher did not stop in 10s; cancelling")
        outbox_task.cancel()

    # FN-3: stop the prompt hot-reload watcher created in PromptManager.
    try:
        prompt_mgr.stop_watcher()
    except Exception:
        logger.debug("prompt watcher stop failed", exc_info=True)

    logger.info("Analysis consumer exited cleanly")
