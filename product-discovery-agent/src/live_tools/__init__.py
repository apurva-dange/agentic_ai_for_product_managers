"""Live tool registry: OpenAI-style function-calling schemas plus dispatch.

Every tool here makes a real network call (via OpenRouterClient.search) -
there is no synthetic data anywhere in this package.
"""

from __future__ import annotations

from typing import Any, Callable

from live_tools import competitor_research, customer_feedback, engineering_effort, risk_and_metrics
from llm.openrouter_client import OpenRouterClient

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "customer_feedback_search",
            "description": (
                "Search the real web (reviews, forums, social posts) for current customer sentiment "
                "about a proposed feature. Public sources only, not internal support data."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "feature_name": {"type": "string", "description": "The feature being evaluated."},
                    "product_category": {
                        "type": "string",
                        "description": "Optional product category to narrow the search, e.g. 'productivity SaaS app'.",
                    },
                },
                "required": ["feature_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "competitor_research",
            "description": "Search the real web for which real competitors offer this feature and how.",
            "parameters": {
                "type": "object",
                "properties": {
                    "feature_name": {"type": "string"},
                    "product_category": {"type": "string", "description": "Optional competitive category to scope the search."},
                },
                "required": ["feature_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "engineering_effort_estimate",
            "description": (
                "Estimate relative engineering effort for a feature, grounded by real web search on how "
                "this class of feature is typically implemented. Not verified against any specific codebase."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "feature_name": {"type": "string"},
                    "platforms": {"type": "array", "items": {"type": "string"}, "description": "Affected platforms, e.g. ['web','ios']."},
                },
                "required": ["feature_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "risk_and_metrics_check",
            "description": (
                "Search the real web for relevant accessibility/privacy/security/legal considerations "
                "for a feature, and propose success metrics."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "feature_name": {"type": "string"},
                    "data_involved": {"type": "array", "items": {"type": "string"}},
                    "user_groups_affected": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["feature_name"],
            },
        },
    },
]

_DISPATCH: dict[str, Callable[..., dict[str, Any]]] = {
    "customer_feedback_search": customer_feedback.run,
    "competitor_research": competitor_research.run,
    "engineering_effort_estimate": engineering_effort.run,
    "risk_and_metrics_check": risk_and_metrics.run,
}


def execute_live_tool(tool_name: str, tool_input: dict[str, Any], client: OpenRouterClient) -> dict[str, Any]:
    """Dispatch a live tool call by name, injecting the shared OpenRouterClient."""

    if tool_name not in _DISPATCH:
        raise KeyError(f"Unknown live tool '{tool_name}'.")
    return _DISPATCH[tool_name](**tool_input, client=client)
