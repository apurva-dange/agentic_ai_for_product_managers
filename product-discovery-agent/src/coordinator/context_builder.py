"""Builds an isolated ContextPackage for each specialist task.

Each agent role gets a different, deliberately narrow slice of context:
the Customer Insights agent gets target users and a known problem
statement, but never platforms or engineering constraints; the Technical
Feasibility agent gets platforms, but never customer comments. This is what
makes context isolation visible rather than just asserted.

Platform and risk-context lookups are reused from Module 1's mock_model.py
instead of being redefined here.
"""

from __future__ import annotations

from typing import Optional

from coordinator.models import AgentTask, ContextPackage, SubagentName
from mock_model import FEATURE_PLATFORMS, FEATURE_RISK_CONTEXT

FEATURE_TARGET_USERS: dict[str, list[str]] = {
    "dark_mode": ["Enterprise users", "SMB users", "Individual users"],
    "mobile_app": ["Field / on-the-go workers", "Mobile-first individual users"],
    "ai_meeting_summary": ["Sales and CS teams on frequent calls", "Product managers running planning meetings"],
    "onboarding": ["New account admins", "New individual users"],
    "export_pdf": ["Finance/ops teams sharing reports", "Compliance-driven enterprise accounts"],
}

FEATURE_KNOWN_PROBLEMS: dict[str, str] = {
    "dark_mode": "Some users report eye strain during evening sessions.",
    "mobile_app": "Users cannot complete core workflows while away from a desktop.",
    "ai_meeting_summary": "Teams manually writing meeting notes lose follow-up items and spend hours summarizing calls.",
    "onboarding": "New accounts struggle to reach first value and often need manual hand-holding to get set up.",
    "export_pdf": "Users cannot easily share or archive reports outside the product.",
}


class ContextPackageBuilder:
    """Builds one ContextPackage per AgentTask, scoped to that agent's role."""

    def build(self, task: AgentTask, feature_key: Optional[str], feature_display_name: str) -> ContextPackage:
        base = {
            "task_id": task.task_id,
            "feature": feature_display_name,
            "objective": task.objective,
        }

        if task.agent_name == SubagentName.CUSTOMER_INSIGHTS:
            return ContextPackage(
                **base,
                allowed_data_sources=["customer_feedback", "product_analytics"],
                target_users=FEATURE_TARGET_USERS.get(feature_key or "", ["All users"]),
                known_problem=FEATURE_KNOWN_PROBLEMS.get(feature_key or "", "Not specified."),
            )

        if task.agent_name == SubagentName.MARKET_RESEARCH:
            return ContextPackage(
                **base,
                allowed_data_sources=["competitors"],
            )

        if task.agent_name == SubagentName.TECHNICAL_FEASIBILITY:
            return ContextPackage(
                **base,
                allowed_data_sources=["engineering_rules"],
                platforms=FEATURE_PLATFORMS.get(feature_key or "", ["web"]),
            )

        if task.agent_name == SubagentName.RISK_AND_METRICS:
            risk_context = FEATURE_RISK_CONTEXT.get(feature_key or "", {})
            return ContextPackage(
                **base,
                allowed_data_sources=["risk_rules"],
                data_involved=risk_context.get("data_involved", []),
                user_groups_affected=risk_context.get("user_groups_affected", ["all users"]),
            )

        raise ValueError(f"No context template defined for agent '{task.agent_name}'.")
