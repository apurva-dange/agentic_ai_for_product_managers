"""Pydantic schemas for the hub-and-spoke multi-agent coordinator (Module 2).

These are additive to - not a replacement for - the Module 1 schemas in
`models.py`. Where a Module 1 concept already fits (e.g. `ToolName`), it is
imported and reused rather than redefined, so there is exactly one source of
truth for shared enums.
"""

from __future__ import annotations

import itertools
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class SubagentName(str, Enum):
    """The four specialist spokes in the hub-and-spoke architecture."""

    CUSTOMER_INSIGHTS = "customer_insights"
    MARKET_RESEARCH = "market_research"
    TECHNICAL_FEASIBILITY = "technical_feasibility"
    RISK_AND_METRICS = "risk_and_metrics"


class AgentStatus(str, Enum):
    """Outcome status for a single subagent invocation."""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


ConfidenceLevel = Literal["low", "medium", "high"]
BriefConfidence = Literal["Low", "Medium", "High"]
BriefRecommendation = Literal[
    "Build now",
    "Add to roadmap",
    "Run an experiment",
    "Investigate further",
    "Do not prioritize",
    "Insufficient evidence",
]


class AgentTask(BaseModel):
    """One unit of delegated work the coordinator hands to a specialist agent."""

    task_id: str
    agent_name: SubagentName
    objective: str
    reason: str
    critical: bool = True


class TaskPlanItem(BaseModel):
    agent_name: SubagentName
    reason: str


class TaskPlan(BaseModel):
    """The coordinator's decomposition of a product question into tasks."""

    feature: str
    tasks: list[AgentTask] = Field(default_factory=list)
    skipped: list[TaskPlanItem] = Field(default_factory=list)


class ContextPackage(BaseModel):
    """An explicit, isolated context package built for exactly one subagent.

    Only the fields relevant to a given agent role are populated; the rest
    stay at their empty defaults. This is what makes context isolation
    visible and testable - a subagent's ContextPackage simply does not carry
    fields it has no business seeing (e.g. the technical agent's package has
    no `known_problem` or `target_users`).
    """

    task_id: str
    feature: str
    objective: str
    allowed_data_sources: list[str] = Field(default_factory=list)

    # Customer Insights fields
    target_users: list[str] = Field(default_factory=list)
    known_problem: Optional[str] = None
    customer_segment_filter: Optional[str] = None

    # Technical Feasibility fields
    platforms: list[str] = Field(default_factory=list)
    technical_constraints: list[str] = Field(default_factory=list)

    # Risk and Metrics fields
    data_involved: list[str] = Field(default_factory=list)
    user_groups_affected: list[str] = Field(default_factory=list)


class AgentResult(BaseModel):
    """The structured outcome of one subagent invocation.

    `data` holds the agent-specific fields described in the project spec
    (e.g. `demand_strength` for Customer Insights, `effort` for Technical
    Feasibility) so that one envelope model can represent all four agent
    shapes without four near-duplicate classes.
    """

    task_id: str
    agent_name: SubagentName
    status: AgentStatus
    summary: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = "low"
    error: Optional[str] = None


class SubagentBriefSection(BaseModel):
    """One agent's contribution to the final decision brief.

    `extra` fields are allowed so each agent can surface its own shape
    (key_evidence, effort, risks, ...) without a separate model per agent.
    """

    model_config = ConfigDict(extra="allow")

    status: Literal["success", "partial", "failed", "skipped"]
    summary: str = ""


class ExperimentProposal(BaseModel):
    objective: str = ""
    target_users: list[str] = Field(default_factory=list)
    success_metrics: list[str] = Field(default_factory=list)
    decision_rule: str = ""


class DecisionBrief(BaseModel):
    """The final, validated, structured output of a coordinator run."""

    feature: str
    decision_question: str
    recommendation: BriefRecommendation
    confidence: BriefConfidence
    executive_summary: str
    customer_insights: SubagentBriefSection
    market_research: SubagentBriefSection
    technical_feasibility: SubagentBriefSection
    risk_and_metrics: SubagentBriefSection
    evidence_gaps: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    recommended_next_steps: list[str] = Field(default_factory=list)
    experiment_proposal: ExperimentProposal = Field(default_factory=ExperimentProposal)
    failed_agents: list[str] = Field(default_factory=list)
    human_decision_required: bool = True


class EventType(str, Enum):
    """Coordinator-level event types, exported into the coordinator trace."""

    REQUEST_RECEIVED = "coordinator_request_received"
    EVIDENCE_REQUIREMENT_IDENTIFIED = "evidence_requirement_identified"
    TASK_CREATED = "task_created"
    SUBAGENT_SKIPPED = "subagent_skipped"
    CONTEXT_PACKAGE_CREATED = "context_package_created"
    SUBAGENT_STARTED = "subagent_started"
    SUBAGENT_TOOL_CALLED = "subagent_tool_called"
    SUBAGENT_COMPLETED = "subagent_completed"
    SUBAGENT_FAILED = "subagent_failed"
    RESULT_VALIDATION_COMPLETED = "result_validation_completed"
    RETRY_ATTEMPTED = "retry_attempted"
    EVIDENCE_GAP_DETECTED = "evidence_gap_detected"
    AGGREGATION_COMPLETED = "aggregation_completed"
    FINAL_DECISION_GENERATED = "final_decision_generated"


_sequence_counter = itertools.count(1)


def next_event_sequence() -> int:
    return next(_sequence_counter)


class CoordinatorEvent(BaseModel):
    """One entry in the coordinator's event history."""

    sequence: int
    event_type: EventType
    timestamp: str
    detail: str
    agent_name: Optional[SubagentName] = None
    task_id: Optional[str] = None

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()
