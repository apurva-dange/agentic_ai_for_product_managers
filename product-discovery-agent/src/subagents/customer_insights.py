"""Customer Insights Agent: evaluates whether meaningful customer demand exists.

Authorized tools: customer_feedback_search, product_analytics_lookup.
It never sees engineering rules, competitor data, or risk rules - those
belong to other spokes.
"""

from __future__ import annotations

from coordinator.models import AgentResult, AgentStatus, AgentTask, ContextPackage, SubagentName
from models import ToolName
from subagents.base import BaseSubagent
from tools.base import ToolExecutionError

DEMAND_THRESHOLDS = {"high": 30, "medium": 15}


def _demand_strength(total_requests: int) -> str:
    if total_requests >= DEMAND_THRESHOLDS["high"]:
        return "high"
    if total_requests >= DEMAND_THRESHOLDS["medium"]:
        return "medium"
    return "low"


class CustomerInsightsAgent(BaseSubagent):
    name = SubagentName.CUSTOMER_INSIGHTS
    allowed_tools = frozenset({ToolName.CUSTOMER_FEEDBACK_SEARCH, ToolName.PRODUCT_ANALYTICS_LOOKUP})

    def run(self, task: AgentTask, context: ContextPackage) -> AgentResult:
        if self.force_failure:
            raise RuntimeError("customer_insights_agent: simulated unhandled execution failure.")

        try:
            feedback = self.call_tool(
                ToolName.CUSTOMER_FEEDBACK_SEARCH,
                feature_name=context.feature,
                customer_segment=context.customer_segment_filter,
            )
        except ToolExecutionError as exc:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                status=AgentStatus.FAILED,
                error=str(exc),
                missing_information=["customer_feedback"],
                confidence="low",
            )

        limitations: list[str] = []
        missing_information: list[str] = []
        try:
            analytics = self.call_tool(ToolName.PRODUCT_ANALYTICS_LOOKUP, feature_name=context.feature)
            limitations.extend(analytics.get("data_limitations", [])[:2])
        except ToolExecutionError:
            missing_information.append("product_analytics")
            limitations.append("Product usage analytics were not available to corroborate feedback demand.")

        total = feedback["total_matching_requests"]
        evidence = feedback["representative_comments"]
        segments = feedback["customer_segments"]
        demand_strength = _demand_strength(total)

        # A contradiction check the agent itself can surface: demand spread
        # thinly across many segments with no dominant segment is weaker
        # signal than concentrated demand, even at the same total count.
        if len(segments) >= 3 and total < DEMAND_THRESHOLDS["high"]:
            limitations.append(
                "Demand is spread across multiple segments rather than concentrated in one, "
                "which weakens the signal at this volume."
            )

        if not evidence:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                status=AgentStatus.PARTIAL,
                summary=f"{total} matching requests were found, but no representative comments were returned.",
                data={"evidence": [], "customer_segments": segments, "demand_strength": demand_strength},
                limitations=limitations,
                missing_information=missing_information + ["representative_comments"],
                confidence="low",
            )

        summary = (
            f"{total} matching customer requests found for '{context.feature}', "
            f"spanning segments: {', '.join(segments)}. Demand strength: {demand_strength}."
        )
        confidence = "high" if demand_strength == "high" and not missing_information else (
            "medium" if demand_strength != "low" else "low"
        )
        status = AgentStatus.PARTIAL if missing_information else AgentStatus.SUCCESS

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            status=status,
            summary=summary,
            data={
                "evidence": evidence,
                "customer_segments": segments,
                "demand_strength": demand_strength,
            },
            limitations=limitations,
            missing_information=missing_information,
            confidence=confidence,
        )
