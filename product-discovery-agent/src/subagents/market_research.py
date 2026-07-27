"""Market Research Agent: evaluates competitive and market context.

Authorized tools: competitor_research only. It never sees raw customer
comments, engineering rules, or risk rules.
"""

from __future__ import annotations

from coordinator.models import AgentResult, AgentStatus, AgentTask, ContextPackage, SubagentName
from models import ToolName
from subagents.base import BaseSubagent
from tools.base import ToolExecutionError


def _market_expectation(offering: list[dict], not_offering: list[dict]) -> str:
    if not offering and not not_offering:
        return "unknown"
    if len(offering) >= 2 and len(offering) >= len(not_offering):
        return "high"
    if offering:
        return "medium"
    return "low"


class MarketResearchAgent(BaseSubagent):
    name = SubagentName.MARKET_RESEARCH
    allowed_tools = frozenset({ToolName.COMPETITOR_RESEARCH})

    def run(self, task: AgentTask, context: ContextPackage) -> AgentResult:
        if self.force_failure:
            raise RuntimeError("market_research_agent: simulated unhandled execution failure.")

        try:
            result = self.call_tool(ToolName.COMPETITOR_RESEARCH, feature_name=context.feature)
        except ToolExecutionError as exc:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                status=AgentStatus.FAILED,
                error=str(exc),
                missing_information=["competitor_research"],
                confidence="low",
            )

        offering = result["competitors_offering"]
        not_offering = result["competitors_not_offering"]
        expectation = _market_expectation(offering, not_offering)

        summary = (
            f"{len(offering)} of {len(offering) + len(not_offering)} tracked (synthetic) "
            f"competitors offer '{context.feature}'. Market expectation: {expectation}."
        )
        confidence = "medium" if offering or not_offering else "low"

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            status=AgentStatus.SUCCESS,
            summary=summary,
            data={
                "competitor_findings": offering,
                "market_expectation": expectation,
                "differentiation_opportunities": result["differentiation_opportunities"],
            },
            limitations=[result["disclaimer"]],
            confidence=confidence,
        )
