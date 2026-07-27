"""Live Risk and Metrics tool: real web search for relevant regulatory /
accessibility considerations (GDPR, CCPA, WCAG, etc.) plus proposed success
metrics for measuring the feature after launch.
"""

from __future__ import annotations

from typing import Any, Optional

from live_tools._shared import run_structured_search
from llm.openrouter_client import OpenRouterClient

JSON_INSTRUCTION = """
Respond with ONLY a JSON object with this exact shape:
{
  "risks": [{"category": "accessibility" | "privacy" | "security" | "legal" | "operational" | "customer_trust", "level": "Low" | "Medium" | "High", "reason": "<short reason>", "recommended_review": "<short review action>"}],
  "human_approval_required": true | false,
  "success_metrics": ["<proposed metric, labelled as proposed not proven>"],
  "experiment_suggestions": ["<short suggestion>"],
  "limitations": ["<what this search could not confirm, e.g. specific to your jurisdiction/industry>"]
}
"""


def run(
    feature_name: str,
    data_involved: Optional[list[str]] = None,
    user_groups_affected: Optional[list[str]] = None,
    client: Optional[OpenRouterClient] = None,
) -> dict[str, Any]:
    """Look up real regulatory/accessibility considerations relevant to a
    feature, plus propose success metrics. This is teaching-purpose research
    support, not a substitute for real legal or compliance review.
    """

    client = client or OpenRouterClient()
    data_clause = f" involving data types: {', '.join(data_involved)}" if data_involved else ""
    users_clause = f" affecting user groups: {', '.join(user_groups_affected)}" if user_groups_affected else ""
    prompt = (
        f"Search the web for real accessibility, privacy, security, and legal considerations relevant "
        f"to a software feature called '{feature_name}'{data_clause}{users_clause} "
        f"(e.g. WCAG, GDPR, CCPA where relevant). Then propose measurable success metrics for this feature."
    )
    result = run_structured_search(client, prompt, JSON_INSTRUCTION)
    result["feature_queried"] = feature_name
    result["data_source"] = "live web search + model reasoning (not a substitute for real legal/compliance review)"
    return result
