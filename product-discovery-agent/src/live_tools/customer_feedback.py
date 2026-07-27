"""Live Customer Feedback Search: real web search for public customer
sentiment (reviews, forum threads, social posts) about a feature.

This does NOT have access to any company's private support tickets - it
searches the public web. That is a real limitation, stated explicitly in
every result, not glossed over.
"""

from __future__ import annotations

from typing import Any, Optional

from live_tools._shared import run_structured_search
from llm.openrouter_client import OpenRouterClient

JSON_INSTRUCTION = """
Respond with ONLY a JSON object with this exact shape:
{
  "total_signal_strength": "low" | "medium" | "high",
  "representative_quotes": [{"source": "<site/forum/app store name>", "quote": "<short paraphrase or quote>", "sentiment": "positive" | "negative" | "neutral"}],
  "segments_mentioned": ["<user type mentioned, if any>"],
  "pain_points": ["<short pain point phrase>"],
  "contradictory_signals": ["<any opposing views found, if any>"],
  "limitations": ["<what this search could NOT determine, e.g. no access to private support tickets>"]
}
Include at most 5 representative_quotes. If you found little or nothing, say so honestly in total_signal_strength="low" and explain in limitations.
"""


def run(feature_name: str, product_category: Optional[str] = None, client: Optional[OpenRouterClient] = None) -> dict[str, Any]:
    """Search the real web for customer sentiment about a feature.

    Args:
        feature_name: The feature being evaluated (e.g. "dark mode").
        product_category: Optional context (e.g. "productivity SaaS app") to
            narrow the search away from unrelated products with the same name.
        client: Injected OpenRouterClient (created lazily if not provided).

    Returns:
        A dict with signal strength, representative quotes with sources,
        segments mentioned, pain points, contradictions, and limitations.
    """

    client = client or OpenRouterClient()
    category_clause = f" in the context of {product_category}" if product_category else ""
    prompt = (
        f"Search the web for real, current customer opinions, reviews, and discussions about "
        f"'{feature_name}'{category_clause}. Look at review sites, forums (e.g. Reddit), and social "
        f"posts. Summarize genuine customer sentiment - do not invent quotes that don't reflect what "
        f"you actually found."
    )
    result = run_structured_search(client, prompt, JSON_INSTRUCTION)
    result["feature_queried"] = feature_name
    result["data_source"] = "live web search (public sources only, not internal support data)"
    return result
