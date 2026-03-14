"""
LLMProvider — abstract interface for pluggable LLM backends.

Replaces direct OllamaClient coupling. Each agent can route to the right
model via the provider interface. Implementations:
  - OllamaProvider: local Ollama/vLLM (fast, free, private)
  - AnthropicProvider: Claude API (deep reasoning, meta-review)
  - Placeholder for GeminiProvider, OpenAIProvider, etc.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    """Abstract interface for any LLM backend."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider identifier for logging/metrics (e.g., 'ollama/qwen3.5')."""

    @property
    @abstractmethod
    def max_context(self) -> int:
        """Maximum context window in tokens."""

    @abstractmethod
    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4000,
        temperature: float = 0.7,
    ) -> dict[str, Any]:
        """Send a chat completion request.

        Returns:
            Dict with keys: content, reasoning (optional), usage, model.
            On error: {"content": "", "error": "<description>"}.
        """

    def is_available(self) -> bool:
        """Health check — can we reach the endpoint?"""
        return True


class OllamaProvider(LLMProvider):
    """Local Ollama/vLLM — wraps existing OllamaClient as LLMProvider."""

    def __init__(
        self,
        base_url: str = "http://spark-ai:11434/v1",
        model: str = "qwen3.5:35b-a3b",
        timeout: int = 180,
    ):
        from rockit_core.agents.llm_client import OllamaClient
        self._client = OllamaClient(base_url=base_url, model=model, timeout=timeout)

    @property
    def provider_name(self) -> str:
        return f"ollama/{self._client.model}"

    @property
    def max_context(self) -> int:
        return 128_000

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4000,
        temperature: float = 0.7,
    ) -> dict[str, Any]:
        return self._client.chat(system_prompt, user_prompt, max_tokens)

    def is_available(self) -> bool:
        return self._client.is_available()

    @property
    def client(self):
        """Access underlying OllamaClient for backward compatibility."""
        return self._client
