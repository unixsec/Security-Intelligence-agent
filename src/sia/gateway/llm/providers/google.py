"""Cloud LLM provider for Google Gemini via REST API."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator

import httpx

from sia.gateway.llm.models import LLMResponse, ModelConfig
from sia.gateway.llm.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class CloudGoogleProvider(BaseLLMProvider):
    """Provider for Gemini models via REST API."""

    def __init__(self, config: ModelConfig):
        super().__init__(config)
        self._api_key = config.api_key
        self._model = config.model_name
        self._timeout = config.timeout_seconds or 120

    def _messages_to_payload(self, messages: list[dict[str, str]]) -> dict:
        system_instruction = None
        contents = []
        for msg in messages:
            if msg["role"] == "system":
                system_instruction = msg["content"]
            elif msg["role"] == "user":
                contents.append({"role": "user", "parts": [{"text": msg["content"]}]})
            elif msg["role"] == "assistant":
                contents.append({"role": "model", "parts": [{"text": msg["content"]}]})
        payload: dict = {"contents": contents}
        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}
        return payload

    def _sync_request(self, url: str, payload: dict) -> dict:
        """Make a synchronous HTTP request via urllib (most compatible)."""
        import urllib.request
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:
            return json.loads(resp.read())

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: object,
    ) -> LLMResponse:
        payload = self._messages_to_payload(messages)
        payload["generationConfig"] = {
            "temperature": temperature or self.config.temperature,
            "maxOutputTokens": max_tokens or self.config.max_tokens,
        }

        url = f"{GEMINI_API_BASE}/{self._model}:generateContent?key={self._api_key}"
        start = time.monotonic()

        logger.info("Gemini request: model=%s payload=%d bytes", self._model, len(json.dumps(payload)))

        data = await asyncio.to_thread(self._sync_request, url, payload)

        latency_ms = int((time.monotonic() - start) * 1000)

        candidates = data.get("candidates", [])
        text = ""
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts)

        usage = data.get("usageMetadata", {})
        input_tokens = usage.get("promptTokenCount", 0)
        output_tokens = usage.get("candidatesTokenCount", 0)

        return LLMResponse(
            content=text,
            model=self._model,
            provider=self.provider_type,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            latency_ms=latency_ms,
            finish_reason="stop",
        )

    async def stream_completion(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: object,
    ) -> AsyncIterator[str]:
        # Fall back to non-streaming for simplicity
        response = await self.chat_completion(
            messages, temperature=temperature, max_tokens=max_tokens, **kwargs
        )
        yield response.content
