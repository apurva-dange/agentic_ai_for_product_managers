"""Tests for ResultAggregator (Module 2 requirements 18, 19, 20)."""

from __future__ import annotations

from coordinator.models import AgentResult, AgentStatus, DecisionBrief, SubagentName, TaskPlan
from coordinator.result_aggregator import ResultAggregator

AGGREGATOR = ResultAggregator()


def _result(agent_name: SubagentName, status: AgentStatus, **data) -> AgentResult:
    return AgentResult(
        task_id=f"task-{agent_name.value}-001",
        agent_name=agent_name,
        status=status,
        summary=f"{agent_name.value} summary",
        data=data,
        confidence="high" if status == AgentStatus.SUCCESS else "low",
    )


def _empty_plan() -> TaskPlan:
    return TaskPlan(feature="dark mode", tasks=[], skipped=[])


def test_aggregator_combines_all_successful_results_into_one_brief() -> None:
    results = {
        SubagentName.CUSTOMER_INSIGHTS: _result(
            SubagentName.CUSTOMER_INSIGHTS, AgentStatus.SUCCESS,
            evidence=[{"id": "FB-1"}], customer_segments=["enterprise"], demand_strength="high",
        ),
        SubagentName.MARKET_RESEARCH: _result(
            SubagentName.MARKET_RESEARCH, AgentStatus.SUCCESS,
            competitor_findings=[{"competitor": "X"}], market_expectation="high", differentiation_opportunities=[],
        ),
        SubagentName.TECHNICAL_FEASIBILITY: _result(
            SubagentName.TECHNICAL_FEASIBILITY, AgentStatus.SUCCESS,
            effort="Low", dependencies=[], affected_systems=["web"],
        ),
        SubagentName.RISK_AND_METRICS: _result(
            SubagentName.RISK_AND_METRICS, AgentStatus.SUCCESS,
            risks=[{"level": "Low", "category": "accessibility"}], success_metrics=["metric A"],
        ),
    }

    brief = AGGREGATOR.aggregate("dark mode", "Should we build dark mode?", results, _empty_plan())

    assert isinstance(brief, DecisionBrief)
    assert brief.confidence == "High"
    assert brief.recommendation in (
        "Build now", "Add to roadmap", "Run an experiment", "Investigate further", "Do not prioritize",
    )
    assert brief.customer_insights.status == "success"
    assert brief.market_research.status == "success"
    assert brief.failed_agents == []
    assert brief.human_decision_required is True


def test_critical_agent_failure_caps_recommendation_and_confidence() -> None:
    results = {
        SubagentName.CUSTOMER_INSIGHTS: AgentResult(
            task_id="task-customer-001", agent_name=SubagentName.CUSTOMER_INSIGHTS,
            status=AgentStatus.FAILED, error="boom", confidence="low",
        ),
        SubagentName.TECHNICAL_FEASIBILITY: _result(
            SubagentName.TECHNICAL_FEASIBILITY, AgentStatus.SUCCESS,
            effort="Low", dependencies=[], affected_systems=["web"],
        ),
    }

    brief = AGGREGATOR.aggregate("dark mode", "Should we build dark mode?", results, _empty_plan())

    assert brief.recommendation == "Investigate further"
    assert brief.confidence == "Low"
    assert "customer_insights" in brief.failed_agents


def test_all_agents_failed_returns_insufficient_evidence() -> None:
    results = {
        name: AgentResult(task_id=f"task-{name.value}", agent_name=name, status=AgentStatus.FAILED, error="boom", confidence="low")
        for name in SubagentName
    }
    brief = AGGREGATOR.aggregate("unknown feature", "Should we do X?", results, _empty_plan())

    assert brief.recommendation == "Insufficient evidence"
    assert brief.confidence == "Low"
    assert brief.human_decision_required is True
    assert set(brief.failed_agents) == {n.value for n in SubagentName}


def test_contradiction_between_high_demand_and_high_effort_is_surfaced() -> None:
    results = {
        SubagentName.CUSTOMER_INSIGHTS: _result(
            SubagentName.CUSTOMER_INSIGHTS, AgentStatus.SUCCESS,
            evidence=[{"id": "FB-1"}], customer_segments=["enterprise"], demand_strength="high",
        ),
        SubagentName.TECHNICAL_FEASIBILITY: _result(
            SubagentName.TECHNICAL_FEASIBILITY, AgentStatus.SUCCESS,
            effort="High", dependencies=["x"], affected_systems=["web"],
        ),
    }
    brief = AGGREGATOR.aggregate("dark mode", "Should we build dark mode?", results, _empty_plan())

    assert brief.contradictions, "expected a contradiction between high demand and high effort"
    assert brief.recommendation != "Build now"


def test_evidence_gaps_reflect_partial_and_skipped_agents() -> None:
    results = {
        SubagentName.CUSTOMER_INSIGHTS: _result(
            SubagentName.CUSTOMER_INSIGHTS, AgentStatus.PARTIAL,
            evidence=[], customer_segments=["enterprise"], demand_strength="low",
        ),
    }
    results[SubagentName.CUSTOMER_INSIGHTS].missing_information.append("representative_comments")
    results[SubagentName.MARKET_RESEARCH] = AgentResult(
        task_id="skipped-market_research", agent_name=SubagentName.MARKET_RESEARCH,
        status=AgentStatus.SKIPPED, summary="Not needed for this scope.", confidence="low",
    )

    brief = AGGREGATOR.aggregate("dark mode", "Should we build dark mode?", results, _empty_plan())

    assert any("representative_comments" in gap for gap in brief.evidence_gaps)
    assert any("skipped" in gap.lower() for gap in brief.evidence_gaps)
