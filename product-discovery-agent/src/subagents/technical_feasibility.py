"""Technical Feasibility Agent: relative implementation effort and risk.

Authorized tools: engineering_effort_estimator only. It never sees customer
comments, competitor data, or risk rules. Requires `platforms` in its
context package - if that field is missing, it raises MissingContextError
rather than guessing or fabricating an estimate.
"""

from __future__ import annotations

from coordinator.models import AgentResult, AgentStatus, AgentTask, ContextPackage, SubagentName
from models import ToolName
from subagents.base import BaseSubagent, MissingContextError
from tools.base import ToolExecutionError


class TechnicalFeasibilityAgent(BaseSubagent):
    name = SubagentName.TECHNICAL_FEASIBILITY
    allowed_tools = frozenset({ToolName.ENGINEERING_EFFORT_ESTIMATOR})

    def run(self, task: AgentTask, context: ContextPackage) -> AgentResult:
        if self.force_failure:
            raise RuntimeError("technical_feasibility_agent: simulated unhandled execution failure.")

        if not context.platforms:
            raise MissingContextError("platforms")

        try:
            result = self.call_tool(
                ToolName.ENGINEERING_EFFORT_ESTIMATOR,
                feature_name=context.feature,
                platforms=context.platforms,
                technical_dependencies=context.technical_constraints or None,
            )
        except ToolExecutionError as exc:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                status=AgentStatus.FAILED,
                error=str(exc),
                missing_information=["engineering_effort"],
                confidence="low",
            )

        effort = result["estimated_effort_level"]
        summary = (
            f"Estimated effort for '{context.feature}' on {', '.join(context.platforms)}: {effort}. "
            f"{result['platforms_note']}"
        )
        confidence = {"Low": "high", "Medium": "medium", "High": "medium", "Unknown": "low"}[effort]

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            status=AgentStatus.SUCCESS,
            summary=summary,
            data={
                "effort": effort,
                "affected_systems": context.platforms,
                "dependencies": result["dependencies"],
                "technical_risks": result["risks"],
                "testing_requirements": result["testing_requirements"],
                "assumptions": [
                    f"Assumes platform scope is limited to: {', '.join(context.platforms)}.",
                    "Assumes the dependencies listed are already available or approved to build against.",
                ],
                "requires_engineering_review": True,
            },
            limitations=[result["disclaimer"]],
            confidence=confidence,
        )
