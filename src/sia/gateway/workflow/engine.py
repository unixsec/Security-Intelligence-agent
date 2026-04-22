"""Native Python workflow engine — replaces Dify Workflow.

YAML-defined workflows with asyncio execution, step-level retry,
variable resolution, and parallel step support.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class WorkflowContext:
    """Execution context shared between workflow steps."""

    workflow_id: str
    run_id: str = field(default_factory=lambda: f"run-{uuid.uuid4().hex[:12]}")
    data: dict[str, Any] = field(default_factory=dict)
    trace_id: str = ""
    started_at: datetime = field(default_factory=datetime.now)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def resolve_ref(self, ref: str) -> Any:
        """Resolve ${variable.path} references against context data."""
        if not isinstance(ref, str) or "${" not in ref:
            return ref

        # Simple single-variable reference: ${foo.bar}
        if ref.startswith("${") and ref.endswith("}") and ref.count("${") == 1:
            path = ref[2:-1].split(".")
            obj: Any = self.data
            for part in path:
                if isinstance(obj, dict):
                    obj = obj.get(part)
                elif hasattr(obj, part):
                    obj = getattr(obj, part)
                else:
                    return None
            return obj

        return ref


class StepRegistry:
    """Registry of available step executors."""

    def __init__(self) -> None:
        self._executors: dict[str, Any] = {}

    def register(self, step_type: str, executor: Any) -> None:
        self._executors[step_type] = executor

    def get(self, step_type: str) -> Any:
        if step_type not in self._executors:
            raise ValueError(f"Unknown step type: {step_type}")
        return self._executors[step_type]


class WorkflowEngine:
    """Native Python workflow engine.

    Loads YAML workflow definitions and executes them with:
    - Sequential and parallel step execution
    - Step-level retry with exponential backoff
    - Variable passing between steps via WorkflowContext
    - Error handling and failure callbacks
    """

    def __init__(self, step_registry: StepRegistry):
        self.step_registry = step_registry
        self._workflows: dict[str, dict] = {}

    def load_workflow(self, yaml_path: str) -> dict:
        """Load a workflow definition from a YAML file."""
        path = Path(yaml_path)
        with path.open() as f:
            wf = yaml.safe_load(f)
        name = wf.get("name", path.stem)
        self._workflows[name] = wf
        logger.info("Loaded workflow: %s (v%s)", name, wf.get("version", "?"))
        return wf

    def load_all(self, workflows_dir: str) -> int:
        """Load all workflow YAML files from a directory."""
        count = 0
        wf_path = Path(workflows_dir)
        if not wf_path.exists():
            logger.warning("Workflows directory not found: %s", workflows_dir)
            return 0
        for yaml_file in wf_path.glob("*.yaml"):
            try:
                self.load_workflow(str(yaml_file))
                count += 1
            except Exception:
                logger.exception("Failed to load workflow: %s", yaml_file)
        return count

    async def execute(
        self, workflow_name: str, context: WorkflowContext | None = None
    ) -> dict[str, Any]:
        """Execute a workflow by name.

        Returns a dict of step_id -> result for all executed steps.
        """
        if workflow_name not in self._workflows:
            raise ValueError(f"Workflow not found: {workflow_name}")

        wf = self._workflows[workflow_name]
        if context is None:
            context = WorkflowContext(workflow_id=workflow_name)

        results: dict[str, Any] = {}
        steps = wf.get("steps", [])

        logger.info(
            "Starting workflow: %s (run_id=%s, steps=%d)",
            workflow_name, context.run_id, len(steps),
        )

        try:
            for step_def in steps:
                step_id = step_def["id"]
                step_type = step_def.get("type", "python_func")

                if step_type == "parallel":
                    # Execute sub-steps in parallel
                    sub_steps = step_def.get("steps", [])
                    async_tasks = [
                        asyncio.create_task(self._execute_step(sub, context))
                        for sub in sub_steps
                    ]
                    sub_results = await asyncio.gather(*async_tasks, return_exceptions=True)

                    # Check for failures — cancel remaining tasks first
                    failed_step = None
                    for sub_def, result in zip(sub_steps, sub_results):
                        if isinstance(result, Exception):
                            failed_step = (sub_def["id"], result)
                            break

                    if failed_step:
                        for t in async_tasks:
                            if not t.done():
                                t.cancel()
                        logger.error("Parallel step %s failed: %s", failed_step[0], failed_step[1])
                        raise failed_step[1]

                    for sub_def, result in zip(sub_steps, sub_results):
                        output_key = sub_def.get("output", sub_def["id"])
                        context.set(output_key, result)
                        results[sub_def["id"]] = result
                else:
                    result = await self._execute_step(step_def, context)
                    output_key = step_def.get("output", step_id)
                    context.set(output_key, result)
                    results[step_id] = result

            logger.info("Workflow %s completed successfully (run_id=%s)", workflow_name, context.run_id)

        except Exception as e:
            logger.error("Workflow %s failed (run_id=%s): %s", workflow_name, context.run_id, e)
            # Execute on_failure handlers
            await self._handle_failure(wf, context, e)
            raise

        return results

    async def _execute_step(
        self, step_def: dict, ctx: WorkflowContext
    ) -> Any:
        """Execute a single workflow step with retry support."""
        step_id = step_def["id"]
        step_type = step_def.get("type", "python_func")
        config = step_def.get("config", {})
        retry_cfg = step_def.get("retry", {})
        max_attempts = retry_cfg.get("max_attempts", 1)

        # Resolve variable references in config
        resolved_config = self._resolve_config(config, ctx)

        executor = self.step_registry.get(step_type)
        step_timeout = step_def.get("timeout_seconds", 300)  # 5 min default

        for attempt in range(1, max_attempts + 1):
            try:
                logger.debug("Executing step %s (attempt %d/%d)", step_id, attempt, max_attempts)
                result = await asyncio.wait_for(
                    executor.execute(resolved_config, ctx),
                    timeout=step_timeout,
                )
                logger.debug("Step %s completed successfully", step_id)
                return result
            except asyncio.TimeoutError:
                logger.error("Step %s timed out after %ds", step_id, step_timeout)
                raise
            except Exception as e:
                if attempt == max_attempts:
                    logger.error("Step %s failed after %d attempts: %s", step_id, max_attempts, e)
                    raise
                delay = self._calc_backoff(retry_cfg, attempt)
                logger.warning(
                    "Step %s failed (attempt %d), retrying in %.1fs: %s",
                    step_id, attempt, delay, e,
                )
                await asyncio.sleep(delay)

        # Should not reach here
        raise RuntimeError(f"Step {step_id} failed unexpectedly")

    def _resolve_config(self, config: dict, ctx: WorkflowContext) -> dict:
        """Recursively resolve ${variable} references in config."""
        resolved: dict = {}
        for key, value in config.items():
            if isinstance(value, str) and "${" in value:
                resolved[key] = ctx.resolve_ref(value)
            elif isinstance(value, dict):
                resolved[key] = self._resolve_config(value, ctx)
            elif isinstance(value, list):
                resolved[key] = [
                    ctx.resolve_ref(v) if isinstance(v, str) and "${" in v else v
                    for v in value
                ]
            else:
                resolved[key] = value
        return resolved

    @staticmethod
    def _calc_backoff(retry_cfg: dict, attempt: int) -> float:
        strategy = retry_cfg.get("backoff", "fixed")
        base = retry_cfg.get("initial_delay_seconds", 1.0)
        max_delay = retry_cfg.get("max_delay_seconds", 60.0)
        if strategy == "exponential":
            return min(base * (2 ** (attempt - 1)), max_delay)
        return base

    async def _handle_failure(
        self, wf: dict, ctx: WorkflowContext, error: Exception
    ) -> None:
        """Execute on_failure handlers."""
        handlers = wf.get("on_failure", [])
        for handler in handlers:
            try:
                handler_type = handler.get("type")
                if handler_type == "alert":
                    msg = handler.get("config", {}).get("message", "Workflow failed")
                    msg = msg.replace("${error_message}", str(error))
                    logger.error("WORKFLOW ALERT: %s", msg)
                elif handler_type == "python_func":
                    func_path = handler.get("config", {}).get("function", "")
                    logger.info("Would call failure handler: %s", func_path)
            except Exception:
                logger.exception("Error in failure handler")

    @property
    def workflow_names(self) -> list[str]:
        return list(self._workflows.keys())
