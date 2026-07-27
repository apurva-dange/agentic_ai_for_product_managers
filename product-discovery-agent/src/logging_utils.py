"""Console event logging for the Product Discovery Agent CLI.

Centralizing the printed output here keeps app.py and agent.py focused on
orchestration, and makes it easy to silence output during tests (verbose=False).
"""

from __future__ import annotations

from typing import Optional

from models import EvidencePlan, ModelResponse, ToolCallRequest, ToolResult, ToolStatus

_RULE = "-" * 72


class EventLogger:
    """Prints a readable trace of the agentic loop as it runs."""

    def __init__(self, verbose: bool = True) -> None:
        self.verbose = verbose

    def _print(self, text: str = "") -> None:
        if self.verbose:
            print(text)

    def log_question(self, question: str) -> None:
        self._print("=" * 72)
        self._print(f"PRODUCT QUESTION: {question}")
        self._print("=" * 72)

    def log_evidence_plan(self, plan: EvidencePlan) -> None:
        needed = ", ".join(e.value for e in plan.required)
        self._print(f"EVIDENCE PLAN: {needed}")
        self._print(_RULE)

    def log_iteration_header(self, iteration: int, max_iterations: int, plan: EvidencePlan) -> None:
        outstanding = ", ".join(e.value for e in plan.outstanding()) or "none"
        self._print(f"\nITERATION {iteration}/{max_iterations} | evidence still required: {outstanding}")

    def log_reasoning(self, summary: str) -> None:
        self._print(f"  reasoning: {summary}")

    def log_tool_call(self, call: ToolCallRequest, forced_failure: bool) -> None:
        note = "  [demo: forcing a transient failure on this call]" if forced_failure else ""
        self._print(f"  selected tool: {call.tool_name.value}")
        self._print(f"  tool input: {call.tool_input}{note}")

    def log_tool_result(self, result: ToolResult, appended: bool) -> None:
        status = "OK" if result.status == ToolStatus.SUCCESS else f"FAILED ({result.error})"
        self._print(f"  tool output status: {status}")
        if not appended:
            self._print("  [BUG MODE] tool result was NOT appended to message history")

    def log_iteration_decision(self, another_iteration_required: bool) -> None:
        self._print(f"  another iteration required: {another_iteration_required}")

    def log_final(self, response: ModelResponse) -> None:
        self._print(f"\nSTOP REASON: end_turn")
        self._print(f"  {response.final_text}")

    def log_unknown_stop_reason(self, response: ModelResponse) -> None:
        self._print(f"\nSTOP REASON: unknown_stop_reason")
        self._print(f"  ERROR: model returned an unsupported stop reason. Halting safely.")
        self._print(f"  details: {response.analysis_summary}")

    def log_max_iterations_reached(self, max_iterations: int) -> None:
        self._print(f"\nSTOP REASON: max_iterations_reached")
        self._print(f"  ERROR: reached the iteration cap ({max_iterations}) before evidence collection completed.")

    def log_recommendation(self, recommendation_json: str) -> None:
        # Always shown, even in --quiet mode: the recommendation is the
        # actual deliverable, not part of the step-by-step trace.
        print("\n" + "=" * 72)
        print("FINAL RECOMMENDATION")
        print("=" * 72)
        print(recommendation_json)

    def log_bug_mode_notice(self, bug_mode: Optional[str]) -> None:
        if bug_mode and bug_mode != "none":
            self._print(f"\n[BUG MODE ACTIVE: {bug_mode}] - intentionally demonstrating a broken agentic loop.\n")
