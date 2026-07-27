"""Deterministic simulated model for the Product Discovery Agent.

This stands in for a real LLM's `messages.create(...)` call. It never
performs free-form generation; instead it looks at the structured
EvidencePlan and returns a deterministic ModelResponse, so the whole demo
runs reliably with no API key and no network access.

An optional real Anthropic-backed model could implement the same
`respond(evidence_plan, iteration) -> ModelResponse` interface and be swapped
in behind an environment variable without changing the agent loop.
"""

from __future__ import annotations

from typing import Optional

from models import (
    EVIDENCE_TO_TOOL,
    EvidencePlan,
    EvidenceType,
    ModelResponse,
    StopReason,
    ToolCallRequest,
    ToolName,
)

EVIDENCE_LABELS: dict[EvidenceType, str] = {
    EvidenceType.CUSTOMER_FEEDBACK: "customer demand",
    EvidenceType.PRODUCT_ANALYTICS: "product usage evidence",
    EvidenceType.COMPETITOR_RESEARCH: "competitor positioning",
    EvidenceType.ENGINEERING_EFFORT: "implementation effort",
    EvidenceType.RISKS: "risk and compliance considerations",
}

TOOL_LABELS: dict[ToolName, str] = {
    ToolName.CUSTOMER_FEEDBACK_SEARCH: "customer feedback search",
    ToolName.PRODUCT_ANALYTICS_LOOKUP: "product analytics lookup",
    ToolName.COMPETITOR_RESEARCH: "competitor research tool",
    ToolName.ENGINEERING_EFFORT_ESTIMATOR: "engineering effort estimator",
    ToolName.RISK_COMPLIANCE_CHECKER: "risk and compliance checker",
}

# Platform context fed to the engineering effort estimator, keyed by feature.
FEATURE_PLATFORMS: dict[str, list[str]] = {
    "dark_mode": ["web"],
    "mobile_app": ["ios", "android"],
    "ai_meeting_summary": ["web"],
    "onboarding": ["web"],
    "export_pdf": ["web"],
}

# Risk-checker context, keyed by feature.
FEATURE_RISK_CONTEXT: dict[str, dict[str, list[str]]] = {
    "dark_mode": {"data_involved": ["UI preference setting"], "user_groups_affected": ["all users"]},
    "mobile_app": {"data_involved": ["auth tokens", "device identifiers"], "user_groups_affected": ["all users"]},
    "ai_meeting_summary": {"data_involved": ["call recordings", "transcripts"], "user_groups_affected": ["meeting participants", "customers on calls"]},
    "onboarding": {"data_involved": ["account setup progress"], "user_groups_affected": ["new users"]},
    "export_pdf": {"data_involved": ["report contents"], "user_groups_affected": ["users who export reports"]},
}


class MockModel:
    """A deterministic stand-in for an LLM's tool-use decision making."""

    def __init__(
        self,
        feature_key: Optional[str],
        feature_display_name: str,
        force_unknown_stop_at_iteration: Optional[int] = None,
    ) -> None:
        self.feature_key = feature_key
        self.feature_display_name = feature_display_name
        self.force_unknown_stop_at_iteration = force_unknown_stop_at_iteration
        self._call_counter = 0

    def respond(self, evidence_plan: EvidencePlan, iteration: int) -> ModelResponse:
        """Produce the next model turn given the current evidence plan."""

        if (
            self.force_unknown_stop_at_iteration is not None
            and iteration == self.force_unknown_stop_at_iteration
        ):
            return ModelResponse(
                stop_reason=StopReason.UNKNOWN,
                analysis_summary=(
                    "Simulated unsupported stop reason returned by the model "
                    "for testing purposes."
                ),
            )

        outstanding = evidence_plan.outstanding()
        if not outstanding:
            return ModelResponse(
                stop_reason=StopReason.END_TURN,
                analysis_summary=self._completion_summary(evidence_plan),
                final_text="Evidence collection complete. Producing the structured recommendation.",
            )

        batch = self._select_batch(outstanding, iteration)
        tool_calls = [self._build_tool_call(evidence_type) for evidence_type in batch]
        return ModelResponse(
            stop_reason=StopReason.TOOL_USE,
            analysis_summary=self._reasoning_summary(evidence_plan, batch),
            tool_calls=tool_calls,
        )

    def _select_batch(
        self, outstanding: list[EvidenceType], iteration: int
    ) -> list[EvidenceType]:
        """Decide which evidence type(s) to pursue this iteration.

        On the first iteration, customer demand and usage analytics are
        independent evidence sources that don't depend on each other, so the
        model requests both tools in a single turn (demonstrating multiple
        tool calls in one response). Later evidence (competitor positioning,
        effort, risk) is gathered one at a time as it becomes relevant.
        """

        if (
            iteration == 1
            and EvidenceType.CUSTOMER_FEEDBACK in outstanding
            and EvidenceType.PRODUCT_ANALYTICS in outstanding
        ):
            return [EvidenceType.CUSTOMER_FEEDBACK, EvidenceType.PRODUCT_ANALYTICS]
        return [outstanding[0]]

    def _build_tool_call(self, evidence_type: EvidenceType) -> ToolCallRequest:
        tool_name = EVIDENCE_TO_TOOL[evidence_type]
        self._call_counter += 1
        tool_call_id = f"call_{self._call_counter:03d}_{tool_name.value}"

        tool_input: dict = {"feature_name": self.feature_display_name}
        if tool_name is ToolName.ENGINEERING_EFFORT_ESTIMATOR:
            tool_input["platforms"] = FEATURE_PLATFORMS.get(self.feature_key or "", ["unspecified"])
        elif tool_name is ToolName.RISK_COMPLIANCE_CHECKER:
            context = FEATURE_RISK_CONTEXT.get(self.feature_key or "", {})
            tool_input["data_involved"] = context.get("data_involved", [])
            tool_input["user_groups_affected"] = context.get("user_groups_affected", [])

        return ToolCallRequest(
            tool_call_id=tool_call_id, tool_name=tool_name, tool_input=tool_input
        )

    def _reasoning_summary(self, plan: EvidencePlan, batch: list[EvidenceType]) -> str:
        if plan.collected:
            established = ", ".join(EVIDENCE_LABELS[e] for e in plan.collected)
            established_txt = f"Established so far: {established}. "
        else:
            established_txt = "No evidence collected yet. "

        calling_labels = [TOOL_LABELS[EVIDENCE_TO_TOOL[e]] for e in batch]
        if len(calling_labels) > 1:
            action = (
                f"The agent will now call {' and '.join(calling_labels)}, "
                "since both are independent evidence sources needed before deeper analysis."
            )
        else:
            still_needed = ", ".join(EVIDENCE_LABELS[e] for e in plan.outstanding())
            action = (
                f"{EVIDENCE_LABELS[batch[0]].capitalize()} is still unknown "
                f"(outstanding: {still_needed}). The agent will now call the "
                f"{calling_labels[0]}."
            )
        return established_txt + action

    def _completion_summary(self, plan: EvidencePlan) -> str:
        established = ", ".join(EVIDENCE_LABELS[e] for e in plan.collected) or "none"
        gaps = ", ".join(EVIDENCE_LABELS[e] for e in plan.permanently_failed)
        summary = f"All actionable evidence has been gathered ({established})."
        if gaps:
            summary += f" Unable to obtain: {gaps} after retries; proceeding with partial evidence."
        return summary
