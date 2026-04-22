"""Tests for the native workflow engine."""

import pytest

from sia.gateway.workflow.engine import StepRegistry, WorkflowContext, WorkflowEngine


class TestWorkflowContext:
    def test_set_and_get(self):
        ctx = WorkflowContext(workflow_id="test")
        ctx.set("key", "value")
        assert ctx.get("key") == "value"

    def test_get_default(self):
        ctx = WorkflowContext(workflow_id="test")
        assert ctx.get("missing", "default") == "default"

    def test_resolve_simple_ref(self):
        ctx = WorkflowContext(workflow_id="test")
        ctx.set("input", {"title": "Test Title"})
        result = ctx.resolve_ref("${input.title}")
        assert result == "Test Title"

    def test_resolve_non_ref(self):
        ctx = WorkflowContext(workflow_id="test")
        assert ctx.resolve_ref("plain string") == "plain string"
        assert ctx.resolve_ref(42) == 42

    def test_resolve_missing_path(self):
        ctx = WorkflowContext(workflow_id="test")
        ctx.set("input", {"title": "Test"})
        result = ctx.resolve_ref("${input.missing}")
        assert result is None

    def test_resolve_nested_path(self):
        ctx = WorkflowContext(workflow_id="test")
        ctx.set("result", {"nested": {"deep": "value"}})
        result = ctx.resolve_ref("${result.nested.deep}")
        assert result == "value"

    def test_run_id_generated(self):
        ctx = WorkflowContext(workflow_id="test")
        assert ctx.run_id.startswith("run-")
        assert len(ctx.run_id) == 16  # "run-" + 12 hex chars


class TestStepRegistry:
    def test_register_and_get(self):
        registry = StepRegistry()
        executor = object()
        registry.register("test_type", executor)
        assert registry.get("test_type") is executor

    def test_get_unknown_raises(self):
        registry = StepRegistry()
        with pytest.raises(ValueError, match="Unknown step type"):
            registry.get("unknown")


class MockStepExecutor:
    def __init__(self, result=None):
        self._result = result or {"status": "ok"}

    async def execute(self, config, ctx):
        return self._result


class TestWorkflowEngine:
    @pytest.fixture
    def engine(self):
        registry = StepRegistry()
        registry.register("python_func", MockStepExecutor({"saved": True}))
        registry.register("llm_call", MockStepExecutor({"analysis": "test"}))
        return WorkflowEngine(registry)

    def test_load_workflow(self, engine, tmp_path):
        wf_file = tmp_path / "test.yaml"
        wf_file.write_text("""
name: test_workflow
version: "1.0"
steps:
  - id: step1
    type: python_func
    config:
      function: "test.func"
""")
        wf = engine.load_workflow(str(wf_file))
        assert wf["name"] == "test_workflow"
        assert "test_workflow" in engine.workflow_names

    @pytest.mark.asyncio
    async def test_execute_simple_workflow(self, engine, tmp_path):
        wf_file = tmp_path / "simple.yaml"
        wf_file.write_text("""
name: simple
version: "1.0"
steps:
  - id: step1
    type: python_func
    config:
      function: "test.func"
""")
        engine.load_workflow(str(wf_file))
        results = await engine.execute("simple")
        assert "step1" in results
        assert results["step1"]["saved"] is True

    @pytest.mark.asyncio
    async def test_execute_parallel_steps(self, engine, tmp_path):
        wf_file = tmp_path / "parallel.yaml"
        wf_file.write_text("""
name: parallel_wf
version: "1.0"
steps:
  - id: parallel_group
    type: parallel
    steps:
      - id: sub1
        type: llm_call
        config:
          prompt: test
      - id: sub2
        type: python_func
        config:
          function: "test.func"
""")
        engine.load_workflow(str(wf_file))
        results = await engine.execute("parallel_wf")
        assert "sub1" in results
        assert "sub2" in results

    @pytest.mark.asyncio
    async def test_execute_nonexistent_workflow_raises(self, engine):
        with pytest.raises(ValueError, match="Workflow not found"):
            await engine.execute("nonexistent")

    def test_load_all_from_directory(self, engine, tmp_path):
        (tmp_path / "wf1.yaml").write_text("name: wf1\nsteps: []")
        (tmp_path / "wf2.yaml").write_text("name: wf2\nsteps: []")
        count = engine.load_all(str(tmp_path))
        assert count == 2

    def test_load_all_missing_dir(self, engine):
        count = engine.load_all("/nonexistent/path")
        assert count == 0


class TestBackoffCalculation:
    def test_fixed_backoff(self):
        delay = WorkflowEngine._calc_backoff(
            {"backoff": "fixed", "initial_delay_seconds": 2.0}, 3
        )
        assert delay == 2.0

    def test_exponential_backoff(self):
        cfg = {"backoff": "exponential", "initial_delay_seconds": 1.0}
        assert WorkflowEngine._calc_backoff(cfg, 1) == 1.0
        assert WorkflowEngine._calc_backoff(cfg, 2) == 2.0
        assert WorkflowEngine._calc_backoff(cfg, 3) == 4.0
        assert WorkflowEngine._calc_backoff(cfg, 4) == 8.0
