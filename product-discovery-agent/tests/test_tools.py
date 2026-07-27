"""Tests for the five local mock tools (requirements 12-16)."""

from __future__ import annotations

import pytest
from tools import competitor_research, customer_feedback, engineering_effort, product_analytics, risk_checker
from tools.base import ToolExecutionError


class TestCustomerFeedbackSearch:
    def test_finds_dark_mode_requests(self) -> None:
        result = customer_feedback.run(feature_name="dark mode")
        assert result["total_matching_requests"] == 42
        assert result["synthetic_data"] is True
        assert len(result["representative_comments"]) > 0
        assert "eye strain during night shifts" in result["related_pain_points"]

    def test_segment_filter_narrows_results(self) -> None:
        result = customer_feedback.run(feature_name="dark mode", customer_segment="enterprise")
        assert result["customer_segments"] == ["enterprise"]
        assert result["returned_record_count"] < result["total_matching_requests"]

    def test_unknown_feature_raises(self) -> None:
        with pytest.raises(ToolExecutionError):
            customer_feedback.run(feature_name="quantum teleportation module")

    def test_force_failure_raises(self) -> None:
        with pytest.raises(ToolExecutionError):
            customer_feedback.run(feature_name="dark mode", force_failure=True)


class TestProductAnalyticsLookup:
    def test_returns_limitations(self) -> None:
        result = product_analytics.run(feature_name="dark mode")
        assert result["data_limitations"], "analytics must always disclose limitations"
        assert "drop_off_rates" in result

    def test_unknown_feature_raises(self) -> None:
        with pytest.raises(ToolExecutionError):
            product_analytics.run(feature_name="not a real feature")


class TestCompetitorResearch:
    def test_marks_synthetic_and_offers(self) -> None:
        result = competitor_research.run(feature_name="mobile app")
        assert result["synthetic_data"] is True
        assert "fictional" in result["disclaimer"].lower()
        assert len(result["competitors_offering"]) > 0

    def test_unknown_feature_raises(self) -> None:
        with pytest.raises(ToolExecutionError):
            competitor_research.run(feature_name="not a real feature")


class TestEngineeringEffortEstimator:
    def test_returns_relative_effort_level(self) -> None:
        result = engineering_effort.run(feature_name="mobile app", platforms=["ios", "android"])
        assert result["estimated_effort_level"] in ("Low", "Medium", "High", "Unknown")
        assert "not a real engineering commitment" in result["disclaimer"]

    def test_merges_extra_dependencies(self) -> None:
        result = engineering_effort.run(feature_name="dark mode", technical_dependencies=["Custom design tool"])
        assert "Custom design tool" in result["dependencies"]

    def test_unknown_feature_raises(self) -> None:
        with pytest.raises(ToolExecutionError):
            engineering_effort.run(feature_name="not a real feature")


class TestRiskComplianceChecker:
    def test_returns_risk_categories(self) -> None:
        result = risk_checker.run(feature_name="ai meeting summary")
        assert result["human_approval_required"] is True
        categories = {r["category"] for r in result["risks"]}
        assert "privacy" in categories

    def test_low_risk_feature_does_not_require_approval(self) -> None:
        result = risk_checker.run(feature_name="dark mode")
        assert result["human_approval_required"] is False

    def test_unknown_feature_raises(self) -> None:
        with pytest.raises(ToolExecutionError):
            risk_checker.run(feature_name="not a real feature")
