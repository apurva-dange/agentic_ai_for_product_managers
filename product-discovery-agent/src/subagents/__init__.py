"""Registry of available specialist subagents, keyed by SubagentName.

The coordinator selects agents from this registry rather than hardcoding a
fixed sequence, so requesting an unregistered name is a normal (handled)
outcome rather than an import-time error.
"""

from __future__ import annotations

from typing import Type

from coordinator.models import SubagentName
from subagents.base import BaseSubagent
from subagents.customer_insights import CustomerInsightsAgent
from subagents.market_research import MarketResearchAgent
from subagents.risk_and_metrics import RiskAndMetricsAgent
from subagents.technical_feasibility import TechnicalFeasibilityAgent

SUBAGENT_REGISTRY: dict[SubagentName, Type[BaseSubagent]] = {
    SubagentName.CUSTOMER_INSIGHTS: CustomerInsightsAgent,
    SubagentName.MARKET_RESEARCH: MarketResearchAgent,
    SubagentName.TECHNICAL_FEASIBILITY: TechnicalFeasibilityAgent,
    SubagentName.RISK_AND_METRICS: RiskAndMetricsAgent,
}
