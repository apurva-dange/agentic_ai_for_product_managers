"""Tests for final recommendation generation and schema validation
(requirements 10, 11)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from models import EvidencePlan, EvidenceType, Recommendation
from recommendations import build_recommendation
from tools import competitor_research, customer_feedback, engineering_effort, product_analytics, risk_checker


def _full_evidence_plan(feature_key: str) -> EvidencePlan:
    plan = EvidencePlan(feature=feature_key, required=list(EvidenceType))
    for evidence_type in EvidenceType:
        plan.mark_collected(evidence_type)
    return plan


def _full_evidence_data(feature_key: str, display_name: str) -> dict[EvidenceType, dict]:
    return {
        EvidenceType.CUSTOMER_FEEDBACK: customer_feedback.run(feature_name=display_name),
        EvidenceType.PRODUCT_ANALYTICS: product_analytics.run(feature_name=display_name),
        EvidenceType.COMPETITOR_RESEARCH: competitor_research.run(feature_name=display_name),
        EvidenceType.ENGINEERING_EFFORT: engineering_effort.run(feature_name=display_name),
        EvidenceType.RISKS: risk_checker.run(feature_name=display_name),
    }


def test_recommendation_schema_rejects_invalid_values() -> None:
    with pytest.raises(ValidationError):
        Recommendation(
            feature="dark mode",
            recommendation="Definitely build it",  # not an allowed literal
            confidence="High",
            executive_summary="x",
        )
    with pytest.raises(ValidationError):
        Recommendation(
            feature="dark mode",
            recommendation="Build now",
            confidence="Very High",  # not an allowed literal
            executive_summary="x",
        )


def test_full_evidence_produces_high_confidence_recommendation() -> None:
    plan = _full_evidence_plan("dark_mode")
    evidence_data = _full_evidence_data("dark_mode", "dark mode")

    recommendation = build_recommendation(
        feature_display_name="dark mode",
        evidence_plan=plan,
        evidence_data=evidence_data,
        stop_reason="end_turn",
        feature_key="dark_mode",
    )

    assert isinstance(recommendation, Recommendation)
    assert recommendation.confidence == "High"
    assert recommendation.recommendation in (
        "Build now",
        "Add to roadmap",
        "Run an experiment",
        "Investigate further",
        "Do not prioritize",
        "Insufficient evidence",
    )
    assert recommendation.human_decision_required is True
    assert len(recommendation.success_metrics) > 0
    assert all("proposed" in metric for metric in recommendation.success_metrics)


def test_no_evidence_produces_insufficient_evidence() -> None:
    plan = EvidencePlan(feature="unknown_feature", required=list(EvidenceType))
    recommendation = build_recommendation(
        feature_display_name="a feature nobody has data for",
        evidence_plan=plan,
        evidence_data={},
        stop_reason="max_iterations_reached",
    )

    assert recommendation.recommendation == "Insufficient evidence"
    assert recommendation.confidence == "Low"
    assert recommendation.human_decision_required is True
    assert recommendation.evidence["customer_feedback"] == []


def test_partial_evidence_never_reaches_high_confidence() -> None:
    plan = EvidencePlan(feature="dark_mode", required=list(EvidenceType))
    plan.mark_collected(EvidenceType.CUSTOMER_FEEDBACK)
    evidence_data = {EvidenceType.CUSTOMER_FEEDBACK: customer_feedback.run(feature_name="dark mode")}

    recommendation = build_recommendation(
        feature_display_name="dark mode",
        evidence_plan=plan,
        evidence_data=evidence_data,
        stop_reason="max_iterations_reached",
        feature_key="dark_mode",
    )

    assert recommendation.confidence == "Low"
    assert recommendation.recommendation != "Build now"
