"""Base LLM provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from sia.gateway.llm.models import LLMResponse, ModelConfig


class BaseLLMProvider(ABC):
    """Abstract base class for all LLM providers."""

    def __init__(self, config: ModelConfig):
        self.config = config

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def provider_type(self) -> str:
        return self.config.provider.value

    @abstractmethod
    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: object,
    ) -> LLMResponse:
        """Send a chat completion request."""
        ...

    @abstractmethod
    async def stream_completion(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: object,
    ) -> AsyncIterator[str]:
        """Stream a chat completion response."""
        ...

    async def close(self) -> None:
        """Clean up resources."""
        pass
