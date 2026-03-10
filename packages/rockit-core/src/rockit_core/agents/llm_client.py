"""
Thin OpenAI-compatible client for Ollama / vLLM.

Uses urllib (stdlib) — no external dependency needed.
Returns {"content": str, "reasoning": str, "usage": dict} or {"content": "", "error": str}.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)


class OllamaClient:
    """Minimal OpenAI-compatible chat client for local LLM inference."""

    def __init__(
        self,
        base_url: str = "http://spark-ai:11434/v1",
        model: str = "qwen3.5:35b-a3b",
        timeout: int = 30,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4000,
    ) -> dict[str, Any]:
        """Send a chat completion request.

        Returns:
            Dict with keys: content, reasoning (if present), usage, model.
            On error: {"content": "", "error": "<description>"}.
        """
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.7,
            "stream": False,
        }

        data = json.dumps(payload).encode("utf-8")
        url = f"{self.base_url}/chat/completions"
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            logger.warning("LLM request failed (URLError): %s", exc)
            return {"content": "", "error": f"URLError: {exc}"}
        except TimeoutError:
            logger.warning("LLM request timed out after %ds", self.timeout)
            return {"content": "", "error": f"Timeout after {self.timeout}s"}
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM request failed: %s", exc)
            return {"content": "", "error": str(exc)}

        return self._parse_response(body)

    @staticmethod
    def _parse_response(body: dict) -> dict[str, Any]:
        """Extract content, reasoning, and usage from OpenAI-compatible response."""
        try:
            choice = body["choices"][0]["message"]
            return {
                "content": choice.get("content", ""),
                "reasoning": choice.get("reasoning", ""),
                "usage": body.get("usage", {}),
                "model": body.get("model", ""),
            }
        except (KeyError, IndexError, TypeError) as exc:
            return {"content": "", "error": f"Parse error: {exc}"}

    def is_available(self) -> bool:
        """Quick health check — can we reach the endpoint?"""
        url = f"{self.base_url}/models"
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=5):
                return True
        except Exception:  # noqa: BLE001
            return False
