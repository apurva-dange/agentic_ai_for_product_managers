"""Validates subagent results before they're allowed into aggregation.

The validator's job is to catch results that claim more than they actually
delivered: a "success" with no evidence, a failed result that somehow still
carries populated findings, or a partial result with no explanation of what
went wrong. It downgrades status rather than crashing, so the coordinator
always has something usable to aggregate.
"""

from __future__ import annotations

from coordinator.models import AgentResult, AgentStatus, SubagentName

REQUIRED_DATA_FIELDS: dict[SubagentName, list[str]] = {
    SubagentName.CUSTOMER_INSIGHTS: ["evidence", "customer_segments", "demand_strength"],
    SubagentName.MARKET_RESEARCH: ["competitor_findings", "market_expectation"],
    SubagentName.TECHNICAL_FEASIBILITY: ["effort", "dependencies"],
    SubagentName.RISK_AND_METRICS: ["risks", "success_metrics"],
}


class ResultValidator:
    """Checks structural completeness and internal consistency of a result."""

    def validate(self, result: AgentResult) -> tuple[AgentResult, list[str]]:
        issues: list[str] = []

        if result.status == AgentStatus.SKIPPED:
            return result, issues

        if result.status == AgentStatus.FAILED:
            required_fields = REQUIRED_DATA_FIELDS.get(result.agent_name, [])
            fabricated = [f for f in required_fields if result.data.get(f)]
            if fabricated:
                issues.append(
                    f"failed result unexpectedly contains populated field(s): {fabricated} "
                    "(evidence must not be fabricated on failure)"
                )
                result = result.model_copy(update={"data": {}})
            return result, issues

        if not result.summary.strip():
            issues.append("summary is empty")

        required_fields = REQUIRED_DATA_FIELDS.get(result.agent_name, [])
        missing_fields = [f for f in required_fields if not result.data.get(f)]
        if missing_fields:
            issues.append(f"missing required field(s): {missing_fields}")
            merged_missing = list(dict.fromkeys(result.missing_information + missing_fields))
            result = result.model_copy(
                update={"status": AgentStatus.PARTIAL, "missing_information": merged_missing}
            )

        if result.status == AgentStatus.PARTIAL and not result.limitations and not result.missing_information:
            issues.append("partial result does not explain what is missing or limited")

        return result, issues
