"""Shared test fixtures."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Force test env before any SIA imports
os.environ["SIA_ENV"] = "test"
os.environ["SIA_DEBUG"] = "true"
os.environ["SIA_MYSQL_HOST"] = "localhost"
os.environ["SIA_REDIS_HOST"] = "localhost"


@pytest.fixture
def llm_response_factory():
    """Factory for creating mock LLM responses."""
    from sia.gateway.llm.models import LLMResponse

    def _create(**overrides):
        defaults = {
            "content": '{"result": "test"}',
            "model": "test-model",
            "provider": "local_openai_compat",
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
            "latency_ms": 200,
            "finish_reason": "stop",
        }
        defaults.update(overrides)
        return LLMResponse(**defaults)

    return _create


@pytest.fixture
def mock_llm_gateway(llm_response_factory):
    """Mock LLM gateway that returns configurable responses."""
    gateway = AsyncMock()
    gateway.chat_completion = AsyncMock(return_value=llm_response_factory())
    gateway.get_provider_status.return_value = {}
    gateway.available_models = ["test-model"]
    return gateway


@pytest.fixture
def mock_prompt_manager():
    """Mock prompt manager."""
    pm = MagicMock()
    pm.render.return_value = [
        {"role": "system", "content": "You are a test assistant"},
        {"role": "user", "content": "Test prompt"},
    ]

    from sia.gateway.llm.prompt_manager import PromptTemplate
    pm.get.return_value = PromptTemplate(
        name="test",
        temperature=0.3,
        max_tokens=1000,
    )
    pm.template_names = ["test"]
    return pm


@pytest.fixture
def sample_intel_data():
    """Sample intelligence data for testing."""
    return {
        "title": "Critical CVE-2025-1234 in OpenSSL",
        "content": "A critical vulnerability was discovered in OpenSSL 3.x that allows remote code execution...",
        "url": "https://example.com/advisory/2025-1234",
        "source_name": "NVD",
        "source_id": 1,
        "published_at": "2025-03-01T12:00:00",
        "cve_id": "CVE-2025-1234",
        "cvss_score": 9.8,
        "epss_score": 0.85,
        "is_kev": True,
    }
