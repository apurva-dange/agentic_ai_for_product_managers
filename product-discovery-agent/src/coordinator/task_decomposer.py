"""Decomposes a product question into specialist tasks.

Every question always needs customer-demand evidence. Whether market
research is worth invoking depends on the nature of the change - a small
copy/wording tweak doesn't need competitor research, so that task is
deliberately skipped (with an explained reason) rather than always running
all four agents.
"""

from __future__ import annotations

import itertools

from coordinator.models import AgentTask, SubagentName, TaskPlan, TaskPlanItem

_TASK_ID_COUNTERS: dict[str, itertools.count] = {}

_TASK_ID_PREFIX = {
    SubagentName.CUSTOMER_INSIGHTS: "customer",
    SubagentName.MARKET_RESEARCH: "market",
    SubagentName.TECHNICAL_FEASIBILITY: "technical",
    SubagentName.RISK_AND_METRICS: "risk",
}

COPY_CHANGE_KEYWORDS = {"copy", "wording", "text", "microcopy", "message", "label", "tooltip"}

OBJECTIVES: dict[SubagentName, str] = {
    SubagentName.CUSTOMER_INSIGHTS: "Determine whether meaningful customer demand exists.",
    SubagentName.MARKET_RESEARCH: "Assess competitive and market positioning.",
    SubagentName.TECHNICAL_FEASIBILITY: "Estimate relative implementation effort and dependencies.",
    SubagentName.RISK_AND_METRICS: "Identify risks and define success metrics.",
}


def _next_task_id(agent_name: SubagentName) -> str:
    prefix = _TASK_ID_PREFIX[agent_name]
    counter = _TASK_ID_COUNTERS.setdefault(prefix, itertools.count(1))
    return f"task-{prefix}-{next(counter):03d}"


class TaskDecomposer:
    """Turns a product question into a TaskPlan of specialist tasks."""

    def build_plan(self, feature_display_name: str, question: str) -> TaskPlan:
        normalized_question = question.lower()
        is_copy_change = any(keyword in normalized_question for keyword in COPY_CHANGE_KEYWORDS)

        tasks: list[AgentTask] = [
            AgentTask(
                task_id=_next_task_id(SubagentName.CUSTOMER_INSIGHTS),
                agent_name=SubagentName.CUSTOMER_INSIGHTS,
                objective=OBJECTIVES[SubagentName.CUSTOMER_INSIGHTS],
                reason="The decision requires evidence of customer demand.",
                critical=True,
            )
        ]
        skipped: list[TaskPlanItem] = []

        if is_copy_change:
            skipped.append(
                TaskPlanItem(
                    agent_name=SubagentName.MARKET_RESEARCH,
                    reason=(
                        "This looks like a low-risk copy/wording change; competitor "
                        "research is unnecessary for this scope."
                    ),
                )
            )
        else:
            tasks.append(
                AgentTask(
                    task_id=_next_task_id(SubagentName.MARKET_RESEARCH),
                    agent_name=SubagentName.MARKET_RESEARCH,
                    objective=OBJECTIVES[SubagentName.MARKET_RESEARCH],
                    reason="The request affects a user-facing feature where competitive context is relevant.",
                    critical=False,
                )
            )

        tasks.append(
            AgentTask(
                task_id=_next_task_id(SubagentName.TECHNICAL_FEASIBILITY),
                agent_name=SubagentName.TECHNICAL_FEASIBILITY,
                objective=OBJECTIVES[SubagentName.TECHNICAL_FEASIBILITY],
                reason="The request affects the product across one or more components and needs an effort estimate.",
                critical=True,
            )
        )
        tasks.append(
            AgentTask(
                task_id=_next_task_id(SubagentName.RISK_AND_METRICS),
                agent_name=SubagentName.RISK_AND_METRICS,
                objective=OBJECTIVES[SubagentName.RISK_AND_METRICS],
                reason="Every feature decision needs risk awareness and a way to measure success.",
                critical=False,
            )
        )

        return TaskPlan(feature=feature_display_name, tasks=tasks, skipped=skipped)
