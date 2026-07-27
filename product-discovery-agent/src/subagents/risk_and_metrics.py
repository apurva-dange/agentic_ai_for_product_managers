"""Risk and Metrics Agent: risk/compliance flags plus proposed success metrics.

Authorized tools: risk_compliance_checker only. Success metrics reuse the
same teaching-purpose SUCCESS_METRICS lookup that Module 1's recommendation
builder already defines, rather than duplicating that data.
"""

from __future__ import annotations

from data_loader import load_dataset, resolve_feature_key
from coordinator.models import AgentResult, AgentStatus, AgentTask, ContextPackage, SubagentName
from models import ToolName
from recommendations import DEFAULT_SUCCESS_METRICS, SUCCESS_METRICS
from subagents.base import BaseSubagent
from tools.base import ToolExecutionError


class RiskAndMetricsAgent(BaseSubagent):
    name = SubagentName.RISK_AND_METRICS
    allowed_tools = frozenset({ToolName.RISK_COMPLIANCE_CHECKER})

    def run(self, task: AgentTask, context: ContextPackage) -> AgentResult:
        if self.force_failure:
            raise RuntimeError("risk_and_metrics_agent: simulated unhandled execution failure.")

        try:
            result = self.call_tool(
                ToolName.RISK_COMPLIANCE_CHECKER,
                feature_name=context.feature,
                data_involved=context.data_involved,
                user_groups_affected=context.user_groups_affected,
            )
        except ToolExecutionError as exc:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                status=AgentStatus.FAILED,
                error=str(exc),
                missing_information=["risk_and_compliance"],
                confidence="low",
            )

        risks = result["risks"]
        required_reviews = [r["recommended_review"] for r in risks]
        feature_key = resolve_feature_key(context.feature, load_dataset("customer_feedback.json"))
        success_metrics = SUCCESS_METRICS.get(feature_key or "", DEFAULT_SUCCESS_METRICS)
        experiment_suggestions = [
            f"Run a limited rollout of '{context.feature}' to a subset of users before a full launch.",
            "Track the proposed success metrics for at least one full usage cycle before deciding.",
        ]

        risk_levels = {r["level"] for r in risks}
        summary = (
            f"Identified {len(risks)} risk item(s) for '{context.feature}' "
            f"(levels: {', '.join(sorted(risk_levels)) or 'none'}). "
            f"Human approval required: {result['human_approval_required']}."
        )
        confidence = "high" if "High" not in risk_levels else "medium"

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            status=AgentStatus.SUCCESS,
            summary=summary,
            data={
                "risks": risks,
                "required_reviews": required_reviews,
                "human_approval_required": result["human_approval_required"],
                "success_metrics": success_metrics,
                "experiment_suggestions": experiment_suggestions,
            },
            limitations=[result["disclaimer"]],
            confidence=confidence,
        )
