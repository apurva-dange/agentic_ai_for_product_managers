"""Coordinator failure-handling tests (Module 2 requirements 13, 14, 15, 16,
17, 21, and spec sections 15.1-15.5)."""

from __future__ import annotations

from coordinator.coordinator import CoordinatorRunConfig, ProductDiscoveryCoordinator
from coordinator.models import AgentStatus, SubagentName
from subagents import SUBAGENT_REGISTRY


def test_market_research_failure_does_not_crash_coordinator_and_lowers_confidence() -> None:
    config = CoordinatorRunConfig(
        question="Should we build dark mode?",
        verbose=False,
        failure_agent=SubagentName.MARKET_RESEARCH,
    )
    result = ProductDiscoveryCoordinator(config).run()

    assert result.results[SubagentName.MARKET_RESEARCH].status == AgentStatus.FAILED
    assert "market_research" in result.brief.failed_agents
    # Other agents still ran and contributed evidence.
    assert result.results[SubagentName.CUSTOMER_INSIGHTS].status == AgentStatus.SUCCESS
    assert result.results[SubagentName.TECHNICAL_FEASIBILITY].status == AgentStatus.SUCCESS
    assert result.brief.confidence in ("Low", "Medium")


def test_failed_agent_evidence_is_not_fabricated() -> None:
    config = CoordinatorRunConfig(
        question="Should we build dark mode?",
        verbose=False,
        failure_agent=SubagentName.MARKET_RESEARCH,
    )
    result = ProductDiscoveryCoordinator(config).run()

    market_section = result.brief.market_research
    assert market_section.status == "failed"
    assert market_section.model_extra.get("key_evidence", []) == []


def test_missing_technical_context_is_detected_and_safely_retried() -> None:
    config = CoordinatorRunConfig(
        question="Should we build dark mode?",
        verbose=False,
        missing_context_agent=SubagentName.TECHNICAL_FEASIBILITY,
    )
    result = ProductDiscoveryCoordinator(config).run()

    # The coordinator supplies a safe fallback (known platform default) and
    # the retry succeeds - no estimate is fabricated without *some* context.
    technical_result = result.results[SubagentName.TECHNICAL_FEASIBILITY]
    assert technical_result.status == AgentStatus.SUCCESS
    assert technical_result.data["effort"] in ("Low", "Medium", "High", "Unknown")

    retry_events = [e for e in result.trace.events if e.event_type.value == "retry_attempted"]
    assert any(e.agent_name == SubagentName.TECHNICAL_FEASIBILITY for e in retry_events)


def test_unknown_critical_agent_stops_safely_without_crashing() -> None:
    reduced_registry = {k: v for k, v in SUBAGENT_REGISTRY.items() if k != SubagentName.TECHNICAL_FEASIBILITY}
    config = CoordinatorRunConfig(
        question="Should we build dark mode?",
        verbose=False,
        subagent_registry=reduced_registry,
    )
    result = ProductDiscoveryCoordinator(config).run()

    assert result.results[SubagentName.TECHNICAL_FEASIBILITY].status == AgentStatus.FAILED
    # Critical failure stops the loop before reaching risk_and_metrics.
    assert SubagentName.RISK_AND_METRICS not in result.results
    assert result.brief.recommendation == "Investigate further"
    assert result.brief.confidence == "Low"


def test_unknown_noncritical_agent_continues_without_stopping() -> None:
    reduced_registry = {k: v for k, v in SUBAGENT_REGISTRY.items() if k != SubagentName.MARKET_RESEARCH}
    config = CoordinatorRunConfig(
        question="Should we build dark mode?",
        verbose=False,
        subagent_registry=reduced_registry,
    )
    result = ProductDiscoveryCoordinator(config).run()

    assert result.results[SubagentName.MARKET_RESEARCH].status == AgentStatus.FAILED
    # Non-critical unknown agent must not stop the rest of the run.
    assert result.results[SubagentName.TECHNICAL_FEASIBILITY].status == AgentStatus.SUCCESS
    assert result.results[SubagentName.RISK_AND_METRICS].status == AgentStatus.SUCCESS


def test_all_agents_failing_returns_insufficient_evidence_and_requires_human_review() -> None:
    config = CoordinatorRunConfig(
        question="Should we add blockchain loyalty rewards?",
        verbose=False,
    )
    result = ProductDiscoveryCoordinator(config).run()

    assert result.brief.recommendation == "Insufficient evidence"
    assert result.brief.confidence == "Low"
    assert result.brief.human_decision_required is True
    assert len(result.brief.failed_agents) == 4
