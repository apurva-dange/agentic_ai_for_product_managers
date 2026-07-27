"""Tests for per-agent tool scoping and authorization (Module 2
requirements 6-10, and spec section 25)."""

from __future__ import annotations

import pytest
from models import ToolName
from subagents.base import ToolNotAuthorizedError
from subagents.customer_insights import CustomerInsightsAgent
from subagents.market_research import MarketResearchAgent
from subagents.risk_and_metrics import RiskAndMetricsAgent
from subagents.technical_feasibility import TechnicalFeasibilityAgent


def test_customer_insights_agent_authorized_tools() -> None:
    agent = CustomerInsightsAgent()
    assert agent.allowed_tools == frozenset(
        {ToolName.CUSTOMER_FEEDBACK_SEARCH, ToolName.PRODUCT_ANALYTICS_LOOKUP}
    )


def test_customer_insights_agent_cannot_use_engineering_estimator() -> None:
    agent = CustomerInsightsAgent()
    with pytest.raises(ToolNotAuthorizedError):
        agent.call_tool(ToolName.ENGINEERING_EFFORT_ESTIMATOR, feature_name="dark mode")


def test_market_research_agent_authorized_tools() -> None:
    agent = MarketResearchAgent()
    assert agent.allowed_tools == frozenset({ToolName.COMPETITOR_RESEARCH})


def test_market_research_agent_cannot_run_risk_checker() -> None:
    agent = MarketResearchAgent()
    with pytest.raises(ToolNotAuthorizedError):
        agent.call_tool(ToolName.RISK_COMPLIANCE_CHECKER, feature_name="dark mode")


def test_technical_feasibility_agent_authorized_tools() -> None:
    agent = TechnicalFeasibilityAgent()
    assert agent.allowed_tools == frozenset({ToolName.ENGINEERING_EFFORT_ESTIMATOR})


def test_technical_feasibility_agent_cannot_search_customer_feedback() -> None:
    agent = TechnicalFeasibilityAgent()
    with pytest.raises(ToolNotAuthorizedError):
        agent.call_tool(ToolName.CUSTOMER_FEEDBACK_SEARCH, feature_name="dark mode")


def test_risk_and_metrics_agent_authorized_tools() -> None:
    agent = RiskAndMetricsAgent()
    assert agent.allowed_tools == frozenset({ToolName.RISK_COMPLIANCE_CHECKER})


def test_risk_and_metrics_agent_cannot_use_competitor_research() -> None:
    agent = RiskAndMetricsAgent()
    with pytest.raises(ToolNotAuthorizedError):
        agent.call_tool(ToolName.COMPETITOR_RESEARCH, feature_name="dark mode")


def test_unauthorized_tool_use_raises_structured_error_not_generic_crash() -> None:
    agent = CustomerInsightsAgent()
    try:
        agent.call_tool(ToolName.RISK_COMPLIANCE_CHECKER, feature_name="dark mode")
        raise AssertionError("expected ToolNotAuthorizedError")
    except ToolNotAuthorizedError as exc:
        assert exc.agent_name == agent.name
        assert exc.tool_name == ToolName.RISK_COMPLIANCE_CHECKER
