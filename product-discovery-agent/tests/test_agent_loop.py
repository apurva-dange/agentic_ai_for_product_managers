"""Tests for the core agentic loop (requirements 1-7)."""

from __future__ import annotations

from agent import ProductDiscoveryAgent, RunConfig
from mock_model import MockModel
from models import EvidencePlan, EvidenceType, StopReason


def test_model_returns_tool_use_with_multiple_calls_on_first_iteration() -> None:
    """Requirement: a response with tool_use, and multiple tools in one iteration."""

    plan = EvidencePlan(feature="dark_mode", required=list(EvidenceType))
    model = MockModel(feature_key="dark_mode", feature_display_name="dark mode")

    response = model.respond(plan, iteration=1)

    assert response.stop_reason == StopReason.TOOL_USE
    assert len(response.tool_calls) == 2  # customer feedback + product analytics bundled together


def test_model_returns_end_turn_when_plan_complete() -> None:
    """Requirement: a final response with end_turn."""

    plan = EvidencePlan(feature="dark_mode", required=list(EvidenceType))
    for evidence_type in EvidenceType:
        plan.mark_collected(evidence_type)
    model = MockModel(feature_key="dark_mode", feature_display_name="dark mode")

    response = model.respond(plan, iteration=6)

    assert response.stop_reason == StopReason.END_TURN
    assert response.final_text


def test_normal_multi_tool_workflow_completes_all_evidence() -> None:
    """Scenario 1: the agent collects all five evidence types before recommending."""

    config = RunConfig(question="Should we build dark mode?", verbose=False)
    result = ProductDiscoveryAgent(config).run()

    assert result.stop_reason == "end_turn"
    assert result.evidence_plan.is_complete()
    assert set(result.evidence_plan.collected) == set(EvidenceType)


def test_multiple_consecutive_tool_calls_across_iterations() -> None:
    """Scenario 2: the agent calls a tool, reviews the result, then calls another."""

    config = RunConfig(question="Should we improve the onboarding process?", verbose=False)
    result = ProductDiscoveryAgent(config).run()

    tool_use_entries = [e for e in result.history.entries if e.tool_call_id]
    tool_names_called = {e.tool_name for e in tool_use_entries if e.tool_name}
    assert len(tool_names_called) == 5
    assert result.iterations_used > 1


def test_tool_results_are_appended_to_history_in_normal_mode() -> None:
    """The agent must never skip adding tool results to history (default mode)."""

    config = RunConfig(question="Should we build dark mode?", verbose=False)
    result = ProductDiscoveryAgent(config).run()

    from models import MessageRole

    tool_result_entries = [e for e in result.history.entries if e.role == MessageRole.TOOL_RESULT]
    assert len(tool_result_entries) == 5


def test_unknown_stop_reason_is_handled_safely() -> None:
    """Scenario 4: an unsupported stop reason must halt safely, not crash or loop forever."""

    config = RunConfig(
        question="Should we build dark mode?",
        verbose=False,
        force_unknown_stop_at_iteration=1,
    )
    result = ProductDiscoveryAgent(config).run()

    assert result.stop_reason == "unknown_stop_reason"
    assert result.recommendation.human_decision_required is True
    assert any("unsupported stop_reason" in e.content for e in result.history.entries)
