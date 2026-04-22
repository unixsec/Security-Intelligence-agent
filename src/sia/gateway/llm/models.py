"""Data models for LLM Gateway."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ProviderType(str, Enum):
    LOCAL_OPENAI_COMPAT = "local_openai_compat"
    CLOUD_ANTHROPIC = "cloud_anthropic"
    CLOUD_GOOGLE = "cloud_google"
    CLOUD_OPENAI = "cloud_openai"


@dataclass
class ModelConfig:
    """Configuration for a single LLM model."""

    name: str
    provider: ProviderType
    endpoint: str = ""
    model_name: str = ""
    api_key: str = ""
    max_tokens: int = 8192
    temperature: float = 0.3
    timeout_seconds: int = 120
    max_retries: int = 3
    proxy: str = ""
    rate_limit_rpm: int = 60
    rate_limit_tpm: int = 100000

    @classmethod
    def from_dict(cls, name: str, data: dict) -> ModelConfig:
        provider_str = data.get("provider", "local_openai_compat")
        return cls(
            name=name,
            provider=ProviderType(provider_str),
            endpoint=data.get("endpoint", ""),
            model_name=data.get("model_name", name),
            api_key=data.get("api_key", ""),
            max_tokens=data.get("max_tokens", 8192),
            temperature=data.get("temperature", 0.3),
            timeout_seconds=data.get("timeout_seconds", 120),
            max_retries=data.get("max_retries", 3),
            proxy=data.get("proxy", "") or data.get("extra", {}).get("proxy", ""),
            rate_limit_rpm=data.get("rate_limit", {}).get("requests_per_minute", 60),
            rate_limit_tpm=data.get("rate_limit", {}).get("tokens_per_minute", 100000),
        )


@dataclass
class LLMResponse:
    """Standardized response from any LLM provider."""

    content: str
    model: str
    provider: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    latency_ms: int = 0
    finish_reason: str = "stop"
    raw_response: dict = field(default_factory=dict)
