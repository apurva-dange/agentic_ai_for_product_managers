"""Thin client for the OpenRouter chat completions API.

This is the ONLY place in the "live" mode that talks to the network. It
wraps two things:

- `chat`: a tool-calling capable chat completion, used to drive the real
  agentic loop (the model decides which tool to call, if any).
- `search`: a call to a web-search-grounded model (Perplexity Sonar via
  OpenRouter), used inside the live tools to fetch real, current
  information instead of returning canned or fabricated text.

Requires OPENROUTER_API_KEY to be set in the environment (e.g. via a local
.env file that is never committed - see .env.example).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

import requests

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_REASONING_MODEL = "anthropic/claude-haiku-4.5"
DEFAULT_SEARCH_MODEL = "perplexity/sonar-pro"
REQUEST_TIMEOUT_SECONDS = 60


class OpenRouterError(Exception):
    """Raised on missing credentials or a non-2xx response from OpenRouter."""


def _load_dotenv_if_present() -> None:
    """Minimal .env loader so OPENROUTER_API_KEY can live in a local,
    gitignored file instead of the shell profile. Only sets variables that
    aren't already in the environment."""

    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def get_api_key() -> str:
    _load_dotenv_if_present()
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise OpenRouterError(
            "OPENROUTER_API_KEY is not set. Add it to a local .env file "
            "(see .env.example) - never pass real keys on the command line "
            "or commit them."
        )
    return api_key


class OpenRouterClient:
    """Wraps the two OpenRouter call shapes this project needs."""

    def __init__(
        self,
        reasoning_model: str = DEFAULT_REASONING_MODEL,
        search_model: str = DEFAULT_SEARCH_MODEL,
    ) -> None:
        self.reasoning_model = reasoning_model
        self.search_model = search_model
        self._api_key = get_api_key()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/apurva-dange/agentic_ai_for_product_managers",
            "X-Title": "Product Discovery Agent (live mode)",
        }

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: str = "auto",
    ) -> dict[str, Any]:
        """A tool-calling capable chat completion for the agent's reasoning loop."""

        payload: dict[str, Any] = {"model": self.reasoning_model, "messages": messages}
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice

        response = requests.post(
            OPENROUTER_URL, headers=self._headers(), json=payload, timeout=REQUEST_TIMEOUT_SECONDS
        )
        if response.status_code >= 400:
            raise OpenRouterError(f"OpenRouter chat call failed ({response.status_code}): {response.text[:500]}")
        return response.json()

    def search(self, prompt: str) -> str:
        """A real, web-search-grounded call (Perplexity Sonar) - used inside
        live tools to fetch current, real information rather than the
        reasoning model's own unaugmented training-data guesses."""

        payload = {
            "model": self.search_model,
            "messages": [{"role": "user", "content": prompt}],
        }
        response = requests.post(
            OPENROUTER_URL, headers=self._headers(), json=payload, timeout=REQUEST_TIMEOUT_SECONDS
        )
        if response.status_code >= 400:
            raise OpenRouterError(f"OpenRouter search call failed ({response.status_code}): {response.text[:500]}")
        data = response.json()
        return data["choices"][0]["message"]["content"]

    @staticmethod
    def extract_json(text: str) -> dict[str, Any]:
        """Best-effort extraction of a JSON object from a model response that
        may include surrounding prose or a markdown code fence."""

        text = text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            raise OpenRouterError(f"Could not find a JSON object in model output: {text[:300]}")
        return json.loads(text[start : end + 1])
