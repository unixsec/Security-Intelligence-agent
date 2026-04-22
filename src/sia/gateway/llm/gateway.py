"""LLM Gateway — unified interface with failover, circuit breaker, and routing."""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator
from datetime import timedelta

from sia.gateway.llm.anonymizer import DataAnonymizer
from sia.gateway.llm.circuit_breaker import CircuitBreaker
from sia.gateway.llm.models import LLMResponse, ModelConfig, ProviderType
from sia.gateway.llm.providers.anthropic import CloudAnthropicProvider
from sia.gateway.llm.providers.base import BaseLLMProvider
from sia.gateway.llm.providers.google import CloudGoogleProvider
from sia.gateway.llm.providers.local_openai import LocalOpenAICompatProvider
from sia.gateway.llm.providers.openai_cloud import CloudOpenAIProvider

logger = logging.getLogger(__name__)

PROVIDER_CLASSES: dict[ProviderType, type[BaseLLMProvider]] = {
    ProviderType.LOCAL_OPENAI_COMPAT: LocalOpenAICompatProvider,
    ProviderType.CLOUD_ANTHROPIC: CloudAnthropicProvider,
    ProviderType.CLOUD_GOOGLE: CloudGoogleProvider,
    ProviderType.CLOUD_OPENAI: CloudOpenAIProvider,
}


class LLMGateway:
    """Unified LLM Gateway with multi-provider failover.

    Features:
    - Multiple provider support (local vLLM + cloud Claude/Gemini/ChatGPT)
    - Automatic failover across configured chains
    - Per-provider circuit breaker
    - Request logging and metrics
    """

    def __init__(self, config: dict):
        self._config = config
        self._providers: dict[str, BaseLLMProvider] = {}
        self._breakers: dict[str, CircuitBreaker] = {}
        self._failover_chains: dict[str, list[str]] = {}
        self._default_model: str = config.get("default_model", "")
        self._anonymizer = DataAnonymizer(config.get("cloud_anonymization"))
        self._cloud_providers: set[str] = set()
        self._init_providers(config)
        self._init_failover(config)

    def _init_providers(self, config: dict) -> None:
        """Initialize all configured LLM providers."""
        models_config = config.get("models", {})
        cb_config = config.get("circuit_breaker", {})

        for model_name, model_data in models_config.items():
            try:
                model_cfg = ModelConfig.from_dict(model_name, model_data)
                provider_cls = PROVIDER_CLASSES.get(model_cfg.provider)
                if provider_cls is None:
                    logger.warning("Unknown provider type for %s: %s", model_name, model_cfg.provider)
                    continue

                self._providers[model_name] = provider_cls(model_cfg)
                if model_cfg.provider in (
                    ProviderType.CLOUD_ANTHROPIC, ProviderType.CLOUD_GOOGLE, ProviderType.CLOUD_OPENAI
                ):
                    self._cloud_providers.add(model_name)
                recovery_secs = cb_config.get("recovery_timeout_seconds", 300)
                self._breakers[model_name] = CircuitBreaker(
                    name=model_name,
                    failure_threshold=cb_config.get("failure_threshold", 5),
                    recovery_timeout=timedelta(seconds=recovery_secs),
                )
                logger.info("Initialized LLM provider: %s (%s)", model_name, model_cfg.provider.value)
            except Exception:
                logger.exception("Failed to initialize provider: %s", model_name)

    def _init_failover(self, config: dict) -> None:
        """Initialize failover chains."""
        failover = config.get("failover", {})
        if failover.get("enabled", False):
            chains = failover.get("chains", {})
            for chain_name, model_list in chains.items():
                # Filter to only models that were successfully initialized
                valid = [m for m in model_list if m in self._providers]
                self._failover_chains[chain_name] = valid

    def _get_chain(self, chain: str = "default") -> list[str]:
        """Get the failover chain for a given name."""
        if chain in self._failover_chains:
            return self._failover_chains[chain]
        # Fall back to single model
        if self._default_model and self._default_model in self._providers:
            return [self._default_model]
        # Fall back to all providers
        return list(self._providers.keys())

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        chain: str = "default",
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: object,
    ) -> LLMResponse:
        """Send a chat completion request with automatic failover.

        Args:
            messages: Chat messages in OpenAI format.
            model: Specific model name, or None to use failover chain.
            chain: Failover chain name (default, high_quality, etc.).
            temperature: Override temperature.
            max_tokens: Override max tokens.

        Returns:
            Standardized LLMResponse.

        Raises:
            RuntimeError: If all providers in the chain fail.
        """
        if model and model in self._providers:
            # Direct model call (no failover)
            return await self._call_provider(
                model, messages, temperature=temperature, max_tokens=max_tokens, **kwargs
            )

        # Failover chain
        chain_models = self._get_chain(chain)
        last_error: Exception | None = None

        for model_name in chain_models:
            breaker = self._breakers.get(model_name)
            if breaker and not breaker.can_execute():
                logger.info("Circuit breaker OPEN for %s, skipping", model_name)
                continue

            try:
                response = await self._call_provider(
                    model_name, messages, temperature=temperature, max_tokens=max_tokens, **kwargs
                )
                if breaker:
                    breaker.record_success()
                return response
            except Exception as e:
                last_error = e
                if breaker:
                    breaker.record_failure()
                logger.warning(
                    "Provider %s failed: %s. Trying next in chain.", model_name, str(e)
                )

        raise RuntimeError(
            f"All providers in chain '{chain}' failed. Last error: {last_error}"
        )

    async def _call_provider(
        self,
        model_name: str,
        messages: list[dict[str, str]],
        **kwargs: object,
    ) -> LLMResponse:
        """Call a specific provider with auto-anonymization for cloud models."""
        provider = self._providers[model_name]
        start = time.monotonic()

        # Anonymize data for cloud providers
        is_cloud = model_name in self._cloud_providers
        anon_ctx = None
        if is_cloud and self._anonymizer.has_patterns:
            messages, anon_ctx = self._anonymizer.anonymize_messages(messages)

        try:
            response = await provider.chat_completion(messages, **kwargs)
            # De-anonymize response content for cloud providers
            if anon_ctx is not None:
                response = LLMResponse(
                    content=self._anonymizer.deanonymize_text(response.content, anon_ctx),
                    model=response.model,
                    provider=response.provider,
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    total_tokens=response.total_tokens,
                    latency_ms=response.latency_ms,
                    finish_reason=response.finish_reason,
                )

            logger.info(
                "LLM call success: model=%s, tokens=%d, latency=%dms",
                model_name, response.total_tokens, response.latency_ms,
            )
            return response
        except Exception:
            logger.exception("LLM call failed: model=%s", model_name)
            raise

    async def stream_completion(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        chain: str = "default",
        **kwargs: object,
    ) -> AsyncIterator[str]:
        """Stream a chat completion response with failover and circuit breaker."""
        if model and model in self._providers:
            chain_models = [model]
        else:
            chain_models = self._get_chain(chain)

        last_error: Exception | None = None

        for model_name in chain_models:
            breaker = self._breakers.get(model_name)
            if breaker and not breaker.can_execute():
                logger.info("Circuit breaker OPEN for %s (stream), skipping", model_name)
                continue

            provider = self._providers.get(model_name)
            if not provider:
                continue

            try:
                async for chunk in provider.stream_completion(messages, **kwargs):
                    yield chunk
                # Stream completed successfully
                if breaker:
                    breaker.record_success()
                return
            except Exception as e:
                last_error = e
                if breaker:
                    breaker.record_failure()
                logger.warning(
                    "Stream provider %s failed: %s. Trying next in chain.", model_name, str(e)
                )

        raise RuntimeError(
            f"All providers in chain '{chain}' failed for stream. Last error: {last_error}"
        )

    def get_provider_status(self) -> dict[str, dict]:
        """Get status of all providers (for health check endpoint)."""
        status = {}
        for name, breaker in self._breakers.items():
            status[name] = {
                "state": breaker.state.value,
                "failure_count": breaker.failure_count,
                "provider_type": self._providers[name].provider_type,
            }
        return status

    @property
    def available_models(self) -> list[str]:
        """List all configured model names."""
        return list(self._providers.keys())

    async def close(self) -> None:
        """Close all provider connections."""
        for provider in self._providers.values():
            try:
                await provider.close()
            except Exception:
                logger.exception("Error closing provider: %s", provider.name)
