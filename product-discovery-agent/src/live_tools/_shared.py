"""Shared helper for live tools: ask a web-search-grounded model a question
and parse its answer into structured JSON, with one retry if parsing fails.
"""

from __future__ import annotations

import json
from typing import Any

from llm.openrouter_client import OpenRouterClient, OpenRouterError


def run_structured_search(client: OpenRouterClient, prompt: str, json_instruction: str) -> dict[str, Any]:
    """Runs a real web-search-grounded query and parses the result as JSON.

    Retries once with a stricter reminder if the first response isn't valid
    JSON - real model output over the network is less predictable than a
    local deterministic function, so this is a genuine (not decorative)
    safety net.
    """

    full_prompt = f"{prompt}\n\n{json_instruction}"
    raw_text = client.search(full_prompt)
    try:
        return client.extract_json(raw_text)
    except (OpenRouterError, json.JSONDecodeError):
        retry_prompt = (
            f"{full_prompt}\n\nYour previous reply could not be parsed as JSON. "
            "Reply with ONLY a single valid JSON object, no prose, no markdown fences."
        )
        raw_text = client.search(retry_prompt)
        return client.extract_json(raw_text)
