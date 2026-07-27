"""Live Engineering Effort Estimator: a real model's judgment, grounded by
web search on how this class of feature is typically implemented.

This is inherently an estimate, not a fact lookup - there is no public API
that knows a specific company's codebase. That limitation is stated
explicitly rather than hidden behind a confident-sounding number.
"""

from __future__ import annotations

from typing import Any, Optional

from live_tools._shared import run_structured_search
from llm.openrouter_client import OpenRouterClient

JSON_INSTRUCTION = """
Respond with ONLY a JSON object with this exact shape:
{
  "estimated_effort_level": "Low" | "Medium" | "High" | "Unknown",
  "typical_implementation_work": ["<short item>"],
  "common_dependencies": ["<short item>"],
  "common_risks": ["<short item>"],
  "testing_considerations": ["<short item>"],
  "confidence": "low" | "medium" | "high",
  "limitations": ["This is a general estimate based on how this type of feature is typically built, not an assessment of any specific company's actual codebase."]
}
"""


def run(
    feature_name: str,
    platforms: Optional[list[str]] = None,
    client: Optional[OpenRouterClient] = None,
) -> dict[str, Any]:
    """Estimate relative engineering effort, grounded by real web search on
    how this class of feature is typically implemented (not a lookup
    against any specific company's real codebase).
    """

    client = client or OpenRouterClient()
    platforms_clause = f" on platforms: {', '.join(platforms)}" if platforms else ""
    prompt = (
        f"Search the web for how software teams typically implement '{feature_name}'{platforms_clause}, "
        "including common engineering blog posts or discussions about the effort, dependencies, and "
        "gotchas involved. Then give a relative effort estimate."
    )
    result = run_structured_search(client, prompt, JSON_INSTRUCTION)
    result["feature_queried"] = feature_name
    result["platforms_considered"] = platforms or ["unspecified"]
    result["data_source"] = "live web search + model reasoning (not verified against a real codebase)"
    return result
