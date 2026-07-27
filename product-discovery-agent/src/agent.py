"""The Product Discovery Agent: evidence planning, tool routing, bug modes.

This module owns everything that is specific to *this* agent (as opposed to
the generic loop mechanics in loop.py): resolving a feature from a free-text
question, building an evidence plan, executing tools, applying retry policy
on failure, and wiring in the two intentional bug-mode demonstrations.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from data_loader import load_dataset, resolve_feature_key
from history import MessageHistory
from logging_utils import EventLogger
from loop import run_loop
from mock_model import MockModel
from models import (
    TOOL_TO_EVIDENCE,
    EvidencePlan,
    EvidenceType,
    ModelResponse,
    Recommendation,
    ToolCallRequest,
    ToolResult,
    ToolStatus,
)
from recommendations import build_recommendation
from tools import execute_tool
from tools.base import ToolExecutionError

MAX_TOOL_RETRIES = 1
DEFAULT_MAX_ITERATIONS = 8


class BugMode(str, Enum):
    """The two intentionally-broken modes used for educational comparison."""

    NONE = "none"
    SKIP_TOOL_HISTORY = "skip-tool-history"
    END_TOO_EARLY = "end-too-early"


@dataclass
class RunConfig:
    """Configuration for a single agent run."""

    question: str
    max_iterations: int = DEFAULT_MAX_ITERATIONS
    bug_mode: BugMode = BugMode.NONE
    demo_failure_target: Optional[EvidenceType] = None
    force_unknown_stop_at_iteration: Optional[int] = None
    verbose: bool = True


@dataclass
class AgentRunResult:
    """Everything a caller needs after a run completes."""

    recommendation: Recommendation
    history: MessageHistory
    evidence_plan: EvidencePlan
    stop_reason: str
    iterations_used: int


def resolve_feature(question: str) -> tuple[Optional[str], str]:
    """Resolve a free-text product question to a known synthetic-data feature key.

    Returns (feature_key, display_name). feature_key is None when the
    question doesn't match any feature in the synthetic datasets - the tools
    will then correctly fail to find data for it, which is how the
    'insufficient evidence' scenario is triggered.
    """

    dataset = load_dataset("customer_feedback.json")
    feature_key = resolve_feature_key(question, dataset)
    display_name = feature_key.replace("_", " ") if feature_key else question
    return feature_key, display_name


def build_evidence_plan(feature_key: Optional[str], question: str) -> EvidencePlan:
    """Create the evidence plan the agent will pursue for this question.

    All five evidence categories are considered relevant to a feature
    decision; which ones actually get *collected* depends on what the model
    decides to call and whether each tool call succeeds.
    """

    return EvidencePlan(feature=feature_key or question, required=list(EvidenceType))


class ProductDiscoveryAgent:
    """Runs the full agentic loop for one product question and returns a recommendation."""

    def __init__(self, config: RunConfig) -> None:
        self.config = config
        self.logger = EventLogger(verbose=config.verbose)
        self.history = MessageHistory()
        self.feature_key, self.feature_display_name = resolve_feature(config.question)
        self.evidence_plan = build_evidence_plan(self.feature_key, config.question)
        self.model = MockModel(
            feature_key=self.feature_key,
            feature_display_name=self.feature_display_name,
            force_unknown_stop_at_iteration=config.force_unknown_stop_at_iteration,
        )
        self.attempts: dict[EvidenceType, int] = {}
        self.evidence_data: dict[EvidenceType, dict] = {}

    def run(self) -> AgentRunResult:
        self.logger.log_bug_mode_notice(self.config.bug_mode.value)
        self.logger.log_question(self.config.question)
        self.history.add_user_message(self.config.question)
        self.logger.log_evidence_plan(self.evidence_plan)

        outcome = run_loop(
            model=self.model,
            history=self.history,
            evidence_plan=self.evidence_plan,
            on_tool_use=self._on_tool_use,
            logger=self.logger,
            max_iterations=self.config.max_iterations,
        )

        recommendation = build_recommendation(
            feature_display_name=self.feature_display_name,
            evidence_plan=self.evidence_plan,
            evidence_data=self.evidence_data,
            stop_reason=outcome.stop_reason,
            feature_key=self.feature_key,
        )
        self.logger.log_recommendation(recommendation.model_dump_json(indent=2))

        return AgentRunResult(
            recommendation=recommendation,
            history=self.history,
            evidence_plan=self.evidence_plan,
            stop_reason=outcome.stop_reason,
            iterations_used=outcome.iterations_used,
        )

    def _on_tool_use(self, response: ModelResponse, iteration: int) -> bool:
        """Execute the tool(s) requested this iteration; return True to stop the loop early.

        This is where `execute_requested_tools` and
        `append_tool_results_to_history` from the required pseudocode live,
        along with the two bug-mode demonstrations.
        """

        calls = response.tool_calls
        if self.config.bug_mode == BugMode.END_TOO_EARLY:
            # BUG: only ever process the first tool call of the first
            # tool_use turn, then stop - never returning the result to the
            # model for another iteration. This is what "ending too early"
            # looks like even when the model asked for more than one tool.
            calls = calls[:1]

        for call in calls:
            self._execute_and_record(call, iteration)

        return self.config.bug_mode == BugMode.END_TOO_EARLY

    def _execute_and_record(self, call: ToolCallRequest, iteration: int) -> None:
        evidence_type = TOOL_TO_EVIDENCE[call.tool_name]
        attempt_no = self.attempts.get(evidence_type, 0)

        tool_input = dict(call.tool_input)
        forced_failure = False
        if self.config.demo_failure_target == evidence_type and attempt_no == 0:
            tool_input["force_failure"] = True
            forced_failure = True

        self.history.add_assistant_tool_use(
            call.tool_name, call.tool_call_id, f"Calling {call.tool_name.value} with input {call.tool_input}"
        )
        self.logger.log_tool_call(call, forced_failure)

        try:
            data = execute_tool(call.tool_name, tool_input)
            result = ToolResult(
                tool_call_id=call.tool_call_id,
                tool_name=call.tool_name,
                status=ToolStatus.SUCCESS,
                data=data,
            )
        except ToolExecutionError as exc:
            result = ToolResult(
                tool_call_id=call.tool_call_id,
                tool_name=call.tool_name,
                status=ToolStatus.FAILURE,
                error=str(exc),
            )
        self.attempts[evidence_type] = attempt_no + 1

        if self.config.bug_mode == BugMode.SKIP_TOOL_HISTORY:
            # BUG: the tool actually ran (see result above) but its result is
            # deliberately never appended to history or evidence state, so
            # the agent's memory of this run never reflects that it happened.
            self.logger.log_tool_result(result, appended=False)
        else:
            summary = self._summarize_result(result)
            self.history.add_tool_result(result, summary)
            self.logger.log_tool_result(result, appended=True)

            if result.status == ToolStatus.SUCCESS:
                self.evidence_plan.mark_collected(evidence_type)
                self.evidence_data[evidence_type] = result.data
            elif self.attempts[evidence_type] > MAX_TOOL_RETRIES:
                self.evidence_plan.mark_permanently_failed(evidence_type)

        self.logger.log_iteration_decision(not self.evidence_plan.is_complete())

    @staticmethod
    def _summarize_result(result: ToolResult) -> str:
        if result.status == ToolStatus.FAILURE:
            return f"FAILURE: {result.error}"
        keys_preview = ", ".join(list(result.data.keys())[:4])
        return f"SUCCESS: returned fields [{keys_preview}, ...]"
