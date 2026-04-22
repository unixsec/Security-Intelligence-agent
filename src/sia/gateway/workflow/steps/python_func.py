"""Workflow step executor: call a Python function by dotted path."""

from __future__ import annotations

import importlib
import logging
from typing import Any

from sia.gateway.workflow.engine import WorkflowContext

logger = logging.getLogger(__name__)


class PythonFuncStepExecutor:
    """Execute a Python function referenced by module:function path."""

    async def execute(self, config: dict, ctx: WorkflowContext) -> Any:
        """Execute a Python function step.

        Config keys:
            function: Dotted path like "sia.analyzer.pipeline:persist_analysis_result"
            args: Dict of keyword arguments
        """
        func_path = config["function"]
        args = config.get("args", {})

        module_path, func_name = func_path.rsplit(":", 1)

        # Defense-in-depth: only allow imports within the sia namespace
        if not module_path.startswith("sia."):
            raise ValueError(
                f"Function path must be within the 'sia' namespace, got: {module_path}"
            )

        module = importlib.import_module(module_path)
        func = getattr(module, func_name)

        logger.debug("Calling function: %s with %d args", func_path, len(args))

        import asyncio
        if asyncio.iscoroutinefunction(func):
            result = await func(ctx=ctx, **args)
        else:
            result = func(ctx=ctx, **args)

        return result
