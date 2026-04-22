"""Cloud LLM provider for Anthropic Claude."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator

from anthropic import AsyncAnthropic

from sia.gateway.llm.models import LLMResponse, ModelConfig
from sia.gateway.llm.providers.base import BaseLLMProvider


class CloudAnthropicProvider(BaseLLMProvider):
    """Provider for Claude models via Anthropic API."""

    def __init__(self, config: ModelConfig):
        super().__init__(config)
        client_kwargs: dict = {"api_key": config.api_key}
        if config.endpoint:
            client_kwargs["base_url"] = config.endpoint
        if config.proxy:
            client_kwargs["proxies"] = config.proxy
        self.client = AsyncAnthropic(**client_kwargs)

    def _convert_messages(
        self, messages: list[dict[str, str]]
    ) -> tuple[str, list[dict[str, str]]]:
        """Convert OpenAI-format messages to Anthropic format.

        Anthropic separates system prompt from messages.
        """
        system_content = ""
        user_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_content += msg["content"] + "\n"
            else:
                user_messages.append({"role": msg["role"], "content": msg["content"]})

        # Anthropic requires at least one user message
        if not user_messages:
            user_messages = [{"role": "user", "content": "Please respond."}]

        return system_content.strip(), user_messages

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: object,
    ) -> LLMResponse:
        system_msg, user_msgs = self._convert_messages(messages)
        start = time.monotonic()

        response = await self.client.messages.create(
            model=self.config.model_name,
            max_tokens=max_tokens or self.config.max_tokens,
            system=system_msg if system_msg else "You are a helpful assistant.",
            messages=user_msgs,  # type: ignore[arg-type]
            temperature=temperature or self.config.temperature,
        )
        latency_ms = int((time.monotonic() - start) * 1000)

        content = ""
        for block in response.content:
            if block.type == "text":
                content += block.text

        return LLMResponse(
            content=content,
            model=response.model,
            provider=self.provider_type,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            total_tokens=response.usage.input_tokens + response.usage.output_tokens,
            latency_ms=latency_ms,
            finish_reason=response.stop_reason or "stop",
        )

    async def stream_completion(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: object,
    ) -> AsyncIterator[str]:
        system_msg, user_msgs = self._convert_messages(messages)

        async with self.client.messages.stream(
            model=self.config.model_name,
            max_tokens=max_tokens or self.config.max_tokens,
            system=system_msg if system_msg else "You are a helpful assistant.",
            messages=user_msgs,  # type: ignore[arg-type]
            temperature=temperature or self.config.temperature,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def close(self) -> None:
        await self.client.close()
