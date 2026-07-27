"""Tests for ResultValidator (Module 2 requirements 11, 12, 17)."""

from __future__ import annotations

from coordinator.models import AgentResult, AgentStatus, SubagentName
from coordinator.result_validator import ResultValidator

VALIDATOR = ResultValidator()


def test_complete_success_result_validates_without_downgrade() -> None:
    result = AgentResult(
        task_id="task-customer-001",
        agent_name=SubagentName.CUSTOMER_INSIGHTS,
        status=AgentStatus.SUCCESS,
        summary="42 matching requests found.",
        data={"evidence": [{"id": "FB-1"}], "customer_segments": ["enterprise"], "demand_strength": "high"},
        confidence="high",
    )
    validated, issues = VALIDATOR.validate(result)
    assert validated.status == AgentStatus.SUCCESS
    assert issues == []


def test_success_with_missing_evidence_is_downgraded_to_partial() -> None:
    result = AgentResult(
        task_id="task-customer-002",
        agent_name=SubagentName.CUSTOMER_INSIGHTS,
        status=AgentStatus.SUCCESS,
        summary="Some requests found, but no comments returned.",
        data={"customer_segments": ["enterprise"], "demand_strength": "low"},  # missing "evidence"
        confidence="medium",
    )
    validated, issues = VALIDATOR.validate(result)
    assert validated.status == AgentStatus.PARTIAL
    assert "evidence" in validated.missing_information
    assert issues


def test_failed_result_cannot_carry_populated_evidence() -> None:
    """A failed result must not be allowed to smuggle in fabricated findings."""

    result = AgentResult(
        task_id="task-market-001",
        agent_name=SubagentName.MARKET_RESEARCH,
        status=AgentStatus.FAILED,
        error="transient failure",
        data={"competitor_findings": [{"competitor": "Fabricated Co"}], "market_expectation": "high"},
    )
    validated, issues = VALIDATOR.validate(result)
    assert validated.data == {}
    assert issues


def test_skipped_result_passes_through_unchanged() -> None:
    result = AgentResult(
        task_id="skipped-market_research",
        agent_name=SubagentName.MARKET_RESEARCH,
        status=AgentStatus.SKIPPED,
        summary="Not needed for this scope.",
    )
    validated, issues = VALIDATOR.validate(result)
    assert validated == result
    assert issues == []


def test_partial_result_without_explanation_is_flagged() -> None:
    result = AgentResult(
        task_id="task-technical-001",
        agent_name=SubagentName.TECHNICAL_FEASIBILITY,
        status=AgentStatus.PARTIAL,
        summary="Some effort data found.",
        data={"effort": "Medium", "dependencies": ["x"]},
        # no limitations, no missing_information - should be flagged
    )
    _, issues = VALIDATOR.validate(result)
    assert any("does not explain" in issue for issue in issues)
