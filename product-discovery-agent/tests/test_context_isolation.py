"""Tests for context package construction and isolation (Module 2
requirements 4 and 5): each subagent gets a focused package and never
inherits the coordinator's full memory or other agents' data."""

from __future__ import annotations

from coordinator.context_builder import ContextPackageBuilder
from coordinator.models import AgentTask, SubagentName

BUILDER = ContextPackageBuilder()


def _task(agent_name: SubagentName) -> AgentTask:
    return AgentTask(
        task_id=f"task-{agent_name.value}-test",
        agent_name=agent_name,
        objective="test objective",
        reason="test reason",
    )


def test_customer_insights_context_has_no_technical_fields() -> None:
    context = BUILDER.build(_task(SubagentName.CUSTOMER_INSIGHTS), "dark_mode", "dark mode")

    assert context.allowed_data_sources == ["customer_feedback", "product_analytics"]
    assert context.target_users
    assert context.known_problem
    # Must not carry technical/risk-only fields.
    assert context.platforms == []
    assert context.technical_constraints == []
    assert context.data_involved == []
    assert context.user_groups_affected == []


def test_technical_feasibility_context_has_no_customer_fields() -> None:
    context = BUILDER.build(_task(SubagentName.TECHNICAL_FEASIBILITY), "dark_mode", "dark mode")

    assert context.allowed_data_sources == ["engineering_rules"]
    assert context.platforms
    # Must not carry customer-only fields.
    assert context.target_users == []
    assert context.known_problem is None


def test_market_research_context_only_has_competitor_source() -> None:
    context = BUILDER.build(_task(SubagentName.MARKET_RESEARCH), "dark_mode", "dark mode")

    assert context.allowed_data_sources == ["competitors"]
    assert context.target_users == []
    assert context.platforms == []
    assert context.data_involved == []


def test_risk_and_metrics_context_only_has_risk_source() -> None:
    context = BUILDER.build(_task(SubagentName.RISK_AND_METRICS), "dark_mode", "dark mode")

    assert context.allowed_data_sources == ["risk_rules"]
    assert context.data_involved
    assert context.user_groups_affected
    assert context.target_users == []
    assert context.platforms == []


def test_context_package_has_no_field_for_other_agents_results_or_history() -> None:
    """A ContextPackage structurally cannot carry coordinator history or
    other agents' results - there is no such field on the model at all."""

    context = BUILDER.build(_task(SubagentName.CUSTOMER_INSIGHTS), "dark_mode", "dark mode")
    field_names = set(type(context).model_fields.keys())
    assert "coordinator_history" not in field_names
    assert "other_agent_results" not in field_names
    assert "message_history" not in field_names
