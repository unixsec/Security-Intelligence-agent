"""Local LLM provider using OpenAI-compatible API (vLLM/Ollama)."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from sia.gateway.llm.models import LLMResponse, ModelConfig
from sia.gateway.llm.providers.base import BaseLLMProvider


class LocalOpenAICompatProvider(BaseLLMProvider):
    """Provider for locally deployed models via OpenAI-compatible API.

    Works with vLLM, Ollama, and any server that implements the
    OpenAI Chat Completions API.
    """

    def __init__(self, config: ModelConfig):
        super().__init__(config)
        self.client = AsyncOpenAI(
            base_url=config.endpoint,
            api_key=config.api_key or "not-needed",
            timeout=config.timeout_seconds,
        )

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: object,
    ) -> LLMResponse:
        start = time.monotonic()
        response = await self.client.chat.completions.create(
            model=self.config.model_name,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature or self.config.temperature,
            max_tokens=max_tokens or self.config.max_tokens,
        )
        latency_ms = int((time.monotonic() - start) * 1000)

        choice = response.choices[0]
        usage = response.usage

        return LLMResponse(
            content=choice.message.content or "",
            model=response.model,
            provider=self.provider_type,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
            latency_ms=latency_ms,
            finish_reason=choice.finish_reason or "stop",
        )

    async def stream_completion(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: object,
    ) -> AsyncIterator[str]:
        stream = await self.client.chat.completions.create(
            model=self.config.model_name,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature or self.config.temperature,
            max_tokens=max_tokens or self.config.max_tokens,
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def close(self) -> None:
        await self.client.close()
