"""Live Competitor Research: real web search for which real products offer
a given feature and how they implement it. No synthetic competitor data -
every name returned came from an actual live search.
"""

from __future__ import annotations

from typing import Any, Optional

from live_tools._shared import run_structured_search
from llm.openrouter_client import OpenRouterClient

JSON_INSTRUCTION = """
Respond with ONLY a JSON object with this exact shape:
{
  "competitors_offering": [{"name": "<real product/company name>", "how_implemented": "<short description>", "source": "<where you found this>"}],
  "competitors_not_offering": ["<real product name known NOT to offer it, if you found any>"],
  "market_expectation": "low" | "medium" | "high",
  "differentiation_opportunities": ["<short idea>"],
  "limitations": ["<what this search could not confirm>"]
}
Only include real products/companies you actually found evidence for - never invent a competitor name.
"""


def run(feature_name: str, product_category: Optional[str] = None, client: Optional[OpenRouterClient] = None) -> dict[str, Any]:
    """Search the real web for competitor/market adoption of a feature.

    Args:
        feature_name: The feature being evaluated (e.g. "dark mode").
        product_category: Optional context to scope the competitive set
            (e.g. "project management SaaS tools").
        client: Injected OpenRouterClient (created lazily if not provided).

    Returns:
        A dict with real competitors offering/not offering the feature,
        market expectation level, differentiation ideas, and limitations.
    """

    client = client or OpenRouterClient()
    category_clause = f" among {product_category}" if product_category else ""
    prompt = (
        f"Search the web for real companies/products{category_clause} that currently offer "
        f"'{feature_name}', and how they implement it. Also note any well-known competitors that "
        f"do NOT offer it, if you can find that. Base this only on what you can actually find."
    )
    result = run_structured_search(client, prompt, JSON_INSTRUCTION)
    result["feature_queried"] = feature_name
    result["data_source"] = "live web search"
    return result
