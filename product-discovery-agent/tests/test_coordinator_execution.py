"""End-to-end coordinator tests: success paths, schema validation, trace
export, and confirmation that Module 1 still works unchanged
(Module 2 requirements 1, 3, 19, 22, 23, 24)."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from coordinator.coordinator import CoordinatorRunConfig, ProductDiscoveryCoordinator
from coordinator.models import AgentStatus, DecisionBrief, SubagentName


def test_coordinator_receives_and_echoes_the_product_question() -> None:
    config = CoordinatorRunConfig(question="Should we build dark mode?", verbose=False)
    result = ProductDiscoveryCoordinator(config).run()

    assert result.brief.decision_question == "Should we build dark mode?"
    assert result.brief.feature == "dark mode"


def test_normal_successful_coordination_runs_all_four_agents() -> None:
    config = CoordinatorRunConfig(question="Should we build dark mode?", verbose=False)
    result = ProductDiscoveryCoordinator(config).run()

    assert set(result.results.keys()) == set(SubagentName)
    assert all(r.status == AgentStatus.SUCCESS for r in result.results.values())
    assert result.brief.failed_agents == []
    assert result.brief.confidence == "High"


def test_unnecessary_agent_is_skipped_for_a_copy_change() -> None:
    config = CoordinatorRunConfig(question="Should we change the onboarding copy?", verbose=False)
    result = ProductDiscoveryCoordinator(config).run()

    assert result.results[SubagentName.MARKET_RESEARCH].status == AgentStatus.SKIPPED
    assert result.results[SubagentName.CUSTOMER_INSIGHTS].status == AgentStatus.SUCCESS


def test_final_output_matches_validated_decision_brief_schema() -> None:
    config = CoordinatorRunConfig(question="Should we build dark mode?", verbose=False)
    result = ProductDiscoveryCoordinator(config).run()

    assert isinstance(result.brief, DecisionBrief)
    # Round-trips through JSON cleanly (schema is fully serializable).
    reloaded = DecisionBrief.model_validate_json(result.brief.model_dump_json())
    assert reloaded.recommendation == result.brief.recommendation


def test_decision_brief_rejects_invalid_recommendation_value() -> None:
    with pytest.raises(ValidationError):
        DecisionBrief(
            feature="dark mode",
            decision_question="Should we build dark mode?",
            recommendation="Definitely do it",  # not an allowed literal
            confidence="High",
            executive_summary="x",
            customer_insights={"status": "success"},
            market_research={"status": "success"},
            technical_feasibility={"status": "success"},
            risk_and_metrics={"status": "success"},
        )


def test_coordinator_trace_can_be_exported_to_json(tmp_path) -> None:
    config = CoordinatorRunConfig(question="Should we build dark mode?", verbose=False)
    result = ProductDiscoveryCoordinator(config).run()

    output_path = tmp_path / "coordinator_trace.json"
    saved_path = result.trace.save_trace(output_path)
    loaded = json.loads(saved_path.read_text())

    assert len(loaded) == len(result.trace.events)
    assert loaded[0]["event_type"] == "coordinator_request_received"


def test_existing_single_agent_mode_still_works() -> None:
    """Module 2 additions must not break the original Module 1 agent."""

    from agent import ProductDiscoveryAgent, RunConfig

    config = RunConfig(question="Should we build dark mode?", verbose=False)
    result = ProductDiscoveryAgent(config).run()

    assert result.stop_reason == "end_turn"
    assert result.recommendation.recommendation == "Build now"
