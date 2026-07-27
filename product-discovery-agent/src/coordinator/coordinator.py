"""ProductDiscoveryCoordinator: the hub in the hub-and-spoke architecture.

The coordinator decomposes a product question into specialist tasks, builds
an isolated context package per task, invokes each subagent through the
shared registry, validates and aggregates their results, and produces one
consolidated DecisionBrief. Subagents never talk to each other - every
result flows back through the coordinator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Type

from agent import resolve_feature
from coordinator.context_builder import ContextPackageBuilder
from coordinator.logging_utils import CoordinatorEventLogger
from coordinator.models import (
    AgentResult,
    AgentStatus,
    AgentTask,
    ContextPackage,
    DecisionBrief,
    EventType,
    SubagentName,
    TaskPlan,
)
from coordinator.result_aggregator import ResultAggregator
from coordinator.result_validator import ResultValidator
from coordinator.retry_policy import RetryPolicy
from coordinator.task_decomposer import TaskDecomposer
from coordinator.trace import CoordinatorTrace
from mock_model import FEATURE_PLATFORMS
from subagents import SUBAGENT_REGISTRY
from subagents.base import BaseSubagent, MissingContextError, SubagentError, UnknownAgentError

RETRYABLE_CONTEXT_FALLBACKS = {"platforms"}


@dataclass
class CoordinatorRunConfig:
    """Configuration for a single coordinator run."""

    question: str
    failure_agent: Optional[SubagentName] = None
    missing_context_agent: Optional[SubagentName] = None
    show_subagent_context: bool = False
    show_task_plan: bool = False
    verbose: bool = True
    subagent_registry: dict[SubagentName, Type[BaseSubagent]] = field(
        default_factory=lambda: dict(SUBAGENT_REGISTRY)
    )


@dataclass
class CoordinatorRunResult:
    """Everything a caller needs after a coordinator run completes."""

    brief: DecisionBrief
    results: dict[SubagentName, AgentResult]
    plan: TaskPlan
    trace: CoordinatorTrace


class ProductDiscoveryCoordinator:
    """Coordinates specialist subagents to produce one product decision brief."""

    def __init__(self, config: CoordinatorRunConfig) -> None:
        self.config = config
        self.logger = CoordinatorEventLogger(verbose=config.verbose)
        self.trace = CoordinatorTrace()
        self.feature_key, self.feature_display_name = resolve_feature(config.question)

        self.decomposer = TaskDecomposer()
        self.context_builder = ContextPackageBuilder()
        self.validator = ResultValidator()
        self.aggregator = ResultAggregator()
        self.retry_policy = RetryPolicy()

    def run(self) -> CoordinatorRunResult:
        self.logger.log_question(self.config.question)
        self.trace.record(EventType.REQUEST_RECEIVED, f"Received product question: '{self.config.question}'")

        plan = self.decomposer.build_plan(self.feature_display_name, self.config.question)
        self.trace.record(
            EventType.EVIDENCE_REQUIREMENT_IDENTIFIED,
            f"Identified {len(plan.tasks)} required evidence area(s); "
            f"{len(plan.skipped)} deemed unnecessary for this question.",
        )
        for task in plan.tasks:
            self.trace.record(EventType.TASK_CREATED, task.reason, agent_name=task.agent_name, task_id=task.task_id)
        for skip in plan.skipped:
            self.trace.record(EventType.SUBAGENT_SKIPPED, skip.reason, agent_name=skip.agent_name)
        self.logger.log_plan(plan, force=self.config.show_task_plan)

        results: dict[SubagentName, AgentResult] = {}

        for skip in plan.skipped:
            results[skip.agent_name] = AgentResult(
                task_id=f"skipped-{skip.agent_name.value}",
                agent_name=skip.agent_name,
                status=AgentStatus.SKIPPED,
                summary=skip.reason,
                confidence="low",
            )

        critical_stop = False
        for task in plan.tasks:
            context = self.context_builder.build(task, self.feature_key, self.feature_display_name)
            self.trace.record(
                EventType.CONTEXT_PACKAGE_CREATED,
                f"Built isolated context package with sources: {context.allowed_data_sources}",
                agent_name=task.agent_name,
                task_id=task.task_id,
            )
            if self.config.show_subagent_context:
                self.logger.log_subagent_context(task.agent_name, context)

            if task.agent_name not in self.config.subagent_registry:
                result = self._unknown_agent_result(task)
                results[task.agent_name] = result
                if task.critical:
                    critical_stop = True
                    break
                continue

            result = self._invoke_subagent(task, context)
            results[task.agent_name] = result

        validated_results: dict[SubagentName, AgentResult] = {}
        for name, result in results.items():
            validated, issues = self.validator.validate(result)
            validated_results[name] = validated
            detail = "no issues" if not issues else "; ".join(issues)
            self.trace.record(EventType.RESULT_VALIDATION_COMPLETED, detail, agent_name=name)

        gaps_preview = [name for name, r in validated_results.items() if r.status != AgentStatus.SUCCESS]
        if gaps_preview:
            self.trace.record(
                EventType.EVIDENCE_GAP_DETECTED,
                f"Evidence gaps present for: {[n.value for n in gaps_preview]}",
            )

        brief = self.aggregator.aggregate(
            feature_display_name=self.feature_display_name,
            decision_question=self.config.question,
            results=validated_results,
            plan=plan,
        )
        self.trace.record(EventType.AGGREGATION_COMPLETED, "Combined validated subagent results into one brief.")
        self.trace.record(
            EventType.FINAL_DECISION_GENERATED,
            f"recommendation='{brief.recommendation}' confidence='{brief.confidence}'"
            + (" (stopped early: critical agent unavailable)" if critical_stop else ""),
        )

        self.logger.log_evidence_gaps(brief)
        self.logger.log_final(brief)

        return CoordinatorRunResult(brief=brief, results=validated_results, plan=plan, trace=self.trace)

    def _unknown_agent_result(self, task: AgentTask) -> AgentResult:
        error = UnknownAgentError(task.agent_name.value)
        self.trace.record(EventType.SUBAGENT_FAILED, str(error), agent_name=task.agent_name, task_id=task.task_id)
        result = AgentResult(
            task_id=task.task_id,
            agent_name=task.agent_name,
            status=AgentStatus.FAILED,
            error=str(error),
            confidence="low",
        )
        self.logger.log_subagent_result(task.agent_name, result)
        return result

    def _invoke_subagent(self, task: AgentTask, context: ContextPackage) -> AgentResult:
        agent_cls = self.config.subagent_registry[task.agent_name]
        force_failure = self.config.failure_agent == task.agent_name
        agent: BaseSubagent = agent_cls(force_failure=force_failure)
        self.logger.log_subagent_start(task.agent_name)
        self.trace.record(EventType.SUBAGENT_STARTED, f"objective='{task.objective}'", agent_name=task.agent_name, task_id=task.task_id)

        working_context = context
        if self.config.missing_context_agent == task.agent_name:
            working_context = context.model_copy(update={"platforms": []})

        attempt = 1
        last_error: Optional[Exception] = None
        while attempt <= self.retry_policy.max_retries + 1:
            try:
                result = agent.run(task, working_context)
                self.trace.record(
                    EventType.SUBAGENT_COMPLETED,
                    f"status={result.status.value}",
                    agent_name=task.agent_name,
                    task_id=task.task_id,
                )
                self.logger.log_subagent_result(task.agent_name, result)
                return result
            except MissingContextError as exc:
                last_error = exc
                has_fallback = exc.field_name in RETRYABLE_CONTEXT_FALLBACKS
                decision = self.retry_policy.evaluate(exc, attempt, has_fallback)
                self.trace.record(
                    EventType.RETRY_ATTEMPTED,
                    f"attempt={attempt} error='{exc}' should_retry={decision.should_retry} reason='{decision.reason}'",
                    agent_name=task.agent_name,
                    task_id=task.task_id,
                )
                self.logger.log_retry(task.agent_name, decision.reason, decision.should_retry)
                if decision.should_retry:
                    fallback_value = FEATURE_PLATFORMS.get(self.feature_key or "", ["web"])
                    working_context = working_context.model_copy(update={"platforms": fallback_value})
                    attempt += 1
                    continue
                break
            except SubagentError as exc:
                last_error = exc
                decision = self.retry_policy.evaluate(exc, attempt, has_fallback=False)
                self.trace.record(
                    EventType.RETRY_ATTEMPTED,
                    f"attempt={attempt} error='{exc}' should_retry={decision.should_retry} reason='{decision.reason}'",
                    agent_name=task.agent_name,
                    task_id=task.task_id,
                )
                self.logger.log_retry(task.agent_name, decision.reason, decision.should_retry)
                break
            except Exception as exc:  # noqa: BLE001 - a genuine subagent crash, handled not swallowed
                last_error = exc
                decision = self.retry_policy.evaluate(exc, attempt, has_fallback=False)
                self.trace.record(
                    EventType.RETRY_ATTEMPTED,
                    f"attempt={attempt} error='{exc}' should_retry={decision.should_retry} reason='{decision.reason}'",
                    agent_name=task.agent_name,
                    task_id=task.task_id,
                )
                self.logger.log_retry(task.agent_name, decision.reason, decision.should_retry)
                break

        error_message = str(last_error) if last_error else "unknown failure"
        missing_information = [last_error.field_name] if isinstance(last_error, MissingContextError) else []
        self.trace.record(
            EventType.SUBAGENT_FAILED, error_message, agent_name=task.agent_name, task_id=task.task_id
        )
        result = AgentResult(
            task_id=task.task_id,
            agent_name=task.agent_name,
            status=AgentStatus.FAILED,
            error=error_message,
            missing_information=missing_information,
            confidence="low",
        )
        self.logger.log_subagent_result(task.agent_name, result)
        return result
