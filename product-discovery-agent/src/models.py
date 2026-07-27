"""Pydantic schemas and enums shared across the Product Discovery Agent.

These models define the structured objects that flow through the agentic
loop: messages, tool calls, tool results, evidence plans, and the final
recommendation. Keeping them centralized makes the loop's contracts explicit
and lets every module validate against the same source of truth.
"""

from __future__ import annotations

import itertools
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class EvidenceType(str, Enum):
    """The categories of evidence the agent can gather via tools."""

    CUSTOMER_FEEDBACK = "customer_feedback"
    PRODUCT_ANALYTICS = "product_analytics"
    COMPETITOR_RESEARCH = "competitor_research"
    ENGINEERING_EFFORT = "engineering_effort"
    RISKS = "risks"


class ToolName(str, Enum):
    """Names of the local mock tools available to the agent."""

    CUSTOMER_FEEDBACK_SEARCH = "customer_feedback_search"
    PRODUCT_ANALYTICS_LOOKUP = "product_analytics_lookup"
    COMPETITOR_RESEARCH = "competitor_research"
    ENGINEERING_EFFORT_ESTIMATOR = "engineering_effort_estimator"
    RISK_COMPLIANCE_CHECKER = "risk_compliance_checker"


TOOL_TO_EVIDENCE: dict[ToolName, EvidenceType] = {
    ToolName.CUSTOMER_FEEDBACK_SEARCH: EvidenceType.CUSTOMER_FEEDBACK,
    ToolName.PRODUCT_ANALYTICS_LOOKUP: EvidenceType.PRODUCT_ANALYTICS,
    ToolName.COMPETITOR_RESEARCH: EvidenceType.COMPETITOR_RESEARCH,
    ToolName.ENGINEERING_EFFORT_ESTIMATOR: EvidenceType.ENGINEERING_EFFORT,
    ToolName.RISK_COMPLIANCE_CHECKER: EvidenceType.RISKS,
}

EVIDENCE_TO_TOOL: dict[EvidenceType, ToolName] = {
    evidence: tool for tool, evidence in TOOL_TO_EVIDENCE.items()
}


class StopReason(str, Enum):
    """Possible stop reasons returned by the (mock or real) model."""

    TOOL_USE = "tool_use"
    END_TURN = "end_turn"
    UNKNOWN = "unknown_stop_reason"


class MessageRole(str, Enum):
    """Roles supported by the structured message history."""

    USER = "user"
    ASSISTANT_ANALYSIS = "assistant_analysis"
    ASSISTANT_TOOL_USE = "assistant_tool_use"
    TOOL_RESULT = "tool_result"
    ASSISTANT_FINAL = "assistant_final"


class ToolStatus(str, Enum):
    """Outcome status for a single tool execution."""

    SUCCESS = "success"
    FAILURE = "failure"


_sequence_counter = itertools.count(1)


def next_sequence_number() -> int:
    """Return a monotonically increasing sequence number for history entries."""

    return next(_sequence_counter)


class ToolCallRequest(BaseModel):
    """A single tool invocation requested by the model in one iteration."""

    tool_call_id: str
    tool_name: ToolName
    tool_input: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    """The outcome of executing a ToolCallRequest."""

    tool_call_id: str
    tool_name: ToolName
    status: ToolStatus
    data: dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class ModelResponse(BaseModel):
    """A single simulated (or real) model turn.

    Mirrors the shape an Anthropic Messages API response would take: a stop
    reason plus either tool-use requests or final text.
    """

    stop_reason: StopReason
    analysis_summary: str = ""
    tool_calls: list[ToolCallRequest] = Field(default_factory=list)
    final_text: str = ""


class HistoryEntry(BaseModel):
    """One entry in the structured conversation history."""

    sequence: int
    role: MessageRole
    content: str
    timestamp: str
    tool_name: Optional[ToolName] = None
    tool_call_id: Optional[str] = None
    status: Optional[ToolStatus] = None

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()


class EvidencePlan(BaseModel):
    """The evidence the agent has decided it needs, and what has been collected.

    `permanently_failed` holds evidence types the agent gave up on after
    exhausting retries; they are excluded from `outstanding()` so the loop
    can terminate instead of retrying forever.
    """

    feature: str
    required: list[EvidenceType]
    collected: list[EvidenceType] = Field(default_factory=list)
    permanently_failed: list[EvidenceType] = Field(default_factory=list)

    def outstanding(self) -> list[EvidenceType]:
        return [
            e
            for e in self.required
            if e not in self.collected and e not in self.permanently_failed
        ]

    def is_complete(self) -> bool:
        return len(self.outstanding()) == 0

    def mark_collected(self, evidence_type: EvidenceType) -> None:
        if evidence_type not in self.collected:
            self.collected.append(evidence_type)
        if evidence_type in self.permanently_failed:
            self.permanently_failed.remove(evidence_type)

    def mark_permanently_failed(self, evidence_type: EvidenceType) -> None:
        if evidence_type not in self.permanently_failed:
            self.permanently_failed.append(evidence_type)


class Recommendation(BaseModel):
    """The final structured product recommendation produced by the agent."""

    feature: str
    recommendation: Literal[
        "Build now",
        "Add to roadmap",
        "Run an experiment",
        "Investigate further",
        "Do not prioritize",
        "Insufficient evidence",
    ]
    confidence: Literal["Low", "Medium", "High"]
    executive_summary: str
    evidence: dict[str, list[Any]] = Field(
        default_factory=lambda: {
            "customer_feedback": [],
            "product_analytics": [],
            "competitor_research": [],
            "engineering_effort": [],
            "risks": [],
        }
    )
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    recommended_next_steps: list[str] = Field(default_factory=list)
    success_metrics: list[str] = Field(default_factory=list)
    human_decision_required: bool = True
