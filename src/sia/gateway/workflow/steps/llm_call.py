"""Workflow step executor: LLM call via the gateway."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from sia.gateway.workflow.engine import WorkflowContext

logger = logging.getLogger(__name__)


class LLMCallStepExecutor:
    """Execute an LLM call step using PromptManager + LLMGateway."""

    def __init__(self, llm_gateway: Any, prompt_manager: Any) -> None:
        self.llm_gateway = llm_gateway
        self.prompt_manager = prompt_manager

    async def execute(self, config: dict, ctx: WorkflowContext) -> dict:
        """Execute an LLM call step.

        Config keys:
            prompt_name: Name of the prompt template
            chain: Failover chain name (default, high_quality, fast)
            variables: Dict of template variables
        """
        prompt_name = config["prompt_name"]
        chain = config.get("chain", "default")
        variables = config.get("variables", {})

        # Render prompt template
        messages = self.prompt_manager.render(prompt_name, **variables)

        # Get prompt config for temperature/max_tokens
        template = self.prompt_manager.get(prompt_name)

        # Call LLM
        response = await self.llm_gateway.chat_completion(
            messages,
            chain=chain,
            temperature=template.temperature,
            max_tokens=template.max_tokens,
        )

        # Parse JSON response
        content = response.content.strip()
        parsed = self._parse_json_response(content)

        # Log call metadata to context
        ctx.set(f"_llm_meta_{prompt_name}", {
            "model": response.model,
            "provider": response.provider,
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "total_tokens": response.total_tokens,
            "tokens": response.total_tokens,  # kept for backwards compatibility
            "latency_ms": response.latency_ms,
        })

        logger.info(
            "LLM step completed: prompt=%s model=%s tokens=%d latency=%dms",
            prompt_name, response.model, response.total_tokens, response.latency_ms,
        )
        return parsed

    @staticmethod
    def _parse_json_response(content: str) -> dict:
        """Parse JSON from LLM response, handling markdown code blocks."""
        # Strip markdown code fences if present
        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*\n?", "", content)
            content = re.sub(r"\n?```\s*$", "", content)

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM JSON response, returning raw content")
            return {"raw_content": content, "_parse_error": True}
