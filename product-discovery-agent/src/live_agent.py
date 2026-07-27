"""Real, internet-connected agentic loop powered by OpenRouter.

Unlike Module 1/2 (a deterministic mock model reasoning over synthetic JSON
data), this runs an actual LLM that decides for itself which tools to call,
grounded by real web search results, until it has enough evidence to answer.
Same tool-use shape as the rest of this project (tool_use -> execute ->
append result -> continue; otherwise -> final answer), just driven by a
real model instead of scripted logic.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from live_tools import TOOL_SCHEMAS, execute_live_tool
from llm.openrouter_client import OpenRouterClient, OpenRouterError

MAX_ITERATIONS = 6

SYSTEM_PROMPT = """You are a Product Discovery Agent helping a product manager evaluate a feature idea.

You have tools that search the REAL web for customer sentiment, competitor adoption, typical \
engineering effort, and risk/compliance considerations. Use them before answering - do not rely \
solely on your own prior knowledge for anything a tool can check for you.

Call as many tools as you need (you do not need to call all of them if a question doesn't warrant \
it), but do not stop until you have enough real evidence to justify a recommendation.

When ready, respond with ONLY a single JSON object (no prose, no markdown fences) shaped exactly like:
{
  "feature": "<feature name>",
  "recommendation": "Build now" | "Add to roadmap" | "Run an experiment" | "Investigate further" | "Do not prioritize" | "Insufficient evidence",
  "confidence": "Low" | "Medium" | "High",
  "executive_summary": "<2-4 sentences>",
  "evidence_summary": {
    "customer_feedback": "<short summary or 'not gathered'>",
    "competitor_research": "<short summary or 'not gathered'>",
    "engineering_effort": "<short summary or 'not gathered'>",
    "risk_and_metrics": "<short summary or 'not gathered'>"
  },
  "assumptions": ["..."],
  "limitations": ["..."],
  "recommended_next_steps": ["..."],
  "success_metrics": ["..."],
  "human_decision_required": true
}

Never claim certainty you don't have. If a search came back weak or contradictory, say so in \
limitations rather than ignoring it. human_decision_required must always be true - you are a \
decision-support tool, not the final decision-maker.
"""


@dataclass
class LiveRunResult:
    final_answer: dict[str, Any]
    transcript: list[dict[str, Any]]
    iterations_used: int


def _fallback_answer(question: str, reason: str) -> dict[str, Any]:
    return {
        "feature": question,
        "recommendation": "Insufficient evidence",
        "confidence": "Low",
        "executive_summary": reason,
        "evidence_summary": {},
        "assumptions": [],
        "limitations": [reason],
        "recommended_next_steps": ["Re-run the question, or narrow its scope."],
        "success_metrics": [],
        "human_decision_required": True,
    }


def run_live_agent(question: str, verbose: bool = True, max_iterations: int = MAX_ITERATIONS) -> LiveRunResult:
    """Runs the real tool-use loop for one product question and returns the
    model's final structured answer, grounded in real tool results."""

    client = OpenRouterClient()
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    if verbose:
        print("=" * 72)
        print("PRODUCT QUESTION (live mode - real LLM + real web search)")
        print(question)
        print("=" * 72)

    iteration = 0
    while iteration < max_iterations:
        iteration += 1
        if verbose:
            print(f"\nITERATION {iteration}/{max_iterations}")

        response = client.chat(messages, tools=TOOL_SCHEMAS, tool_choice="auto")
        choice = response["choices"][0]
        message = choice["message"]
        tool_calls = message.get("tool_calls")

        if tool_calls:
            messages.append(message)
            for call in tool_calls:
                name = call["function"]["name"]
                try:
                    arguments = json.loads(call["function"]["arguments"] or "{}")
                except json.JSONDecodeError:
                    arguments = {}
                if verbose:
                    print(f"  tool call: {name}({arguments})")

                try:
                    result = execute_live_tool(name, arguments, client)
                    status = "success"
                except (OpenRouterError, KeyError, TypeError) as exc:
                    result = {"error": str(exc)}
                    status = "failed"
                if verbose:
                    print(f"  tool result status: {status}")

                messages.append(
                    {"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result)}
                )
            continue

        content = message.get("content", "") or ""
        try:
            final_answer = client.extract_json(content)
        except (OpenRouterError, json.JSONDecodeError):
            final_answer = _fallback_answer(
                question, "Model did not return the requested structured JSON format: " + content[:300]
            )
        if verbose:
            print("\nFINAL ANSWER")
            print(json.dumps(final_answer, indent=2))
        return LiveRunResult(final_answer=final_answer, transcript=messages, iterations_used=iteration)

    fallback = _fallback_answer(
        question, f"Stopped after reaching the {max_iterations}-iteration tool-call cap without a final answer."
    )
    if verbose:
        print("\nSTOPPED: reached max iterations without a final answer.")
    return LiveRunResult(final_answer=fallback, transcript=messages, iterations_used=max_iterations)
