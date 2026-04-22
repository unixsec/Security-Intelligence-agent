"""Tests for LLM call step executor."""

import pytest

from sia.gateway.workflow.engine import WorkflowContext
from sia.gateway.workflow.steps.llm_call import LLMCallStepExecutor


class TestLLMCallStep:
    @pytest.fixture
    def executor(self, mock_llm_gateway, mock_prompt_manager):
        return LLMCallStepExecutor(mock_llm_gateway, mock_prompt_manager)

    @pytest.mark.asyncio
    async def test_execute_basic(self, executor, mock_llm_gateway, llm_response_factory):
        mock_llm_gateway.chat_completion.return_value = llm_response_factory(
            content='{"category": "vulnerability", "severity": "high"}'
        )
        ctx = WorkflowContext(workflow_id="test")
        config = {
            "prompt_name": "test",
            "chain": "default",
            "variables": {"title": "Test"},
        }
        result = await executor.execute(config, ctx)
        assert result["category"] == "vulnerability"
        assert result["severity"] == "high"

    @pytest.mark.asyncio
    async def test_parse_json_with_code_fences(self, executor, mock_llm_gateway, llm_response_factory):
        mock_llm_gateway.chat_completion.return_value = llm_response_factory(
            content='```json\n{"key": "value"}\n```'
        )
        ctx = WorkflowContext(workflow_id="test")
        config = {"prompt_name": "test", "variables": {}}
        result = await executor.execute(config, ctx)
        assert result["key"] == "value"

    @pytest.mark.asyncio
    async def test_parse_invalid_json(self, executor, mock_llm_gateway, llm_response_factory):
        mock_llm_gateway.chat_completion.return_value = llm_response_factory(
            content="This is not JSON"
        )
        ctx = WorkflowContext(workflow_id="test")
        config = {"prompt_name": "test", "variables": {}}
        result = await executor.execute(config, ctx)
        assert result["_parse_error"] is True
        assert "This is not JSON" in result["raw_content"]

    @pytest.mark.asyncio
    async def test_llm_metadata_stored_in_context(self, executor, mock_llm_gateway, llm_response_factory):
        mock_llm_gateway.chat_completion.return_value = llm_response_factory(
            content='{"ok": true}', model="deepseek-r1", total_tokens=500
        )
        ctx = WorkflowContext(workflow_id="test")
        config = {"prompt_name": "test", "variables": {}}
        await executor.execute(config, ctx)
        meta = ctx.get("_llm_meta_test")
        assert meta is not None
        assert meta["model"] == "deepseek-r1"
        assert meta["tokens"] == 500


class TestJSONParsing:
    def test_plain_json(self):
        result = LLMCallStepExecutor._parse_json_response('{"a": 1}')
        assert result == {"a": 1}

    def test_json_with_markdown_fence(self):
        result = LLMCallStepExecutor._parse_json_response('```json\n{"a": 1}\n```')
        assert result == {"a": 1}

    def test_json_with_plain_fence(self):
        result = LLMCallStepExecutor._parse_json_response('```\n{"a": 1}\n```')
        assert result == {"a": 1}

    def test_invalid_json_returns_raw(self):
        result = LLMCallStepExecutor._parse_json_response("not json")
        assert result["_parse_error"] is True
