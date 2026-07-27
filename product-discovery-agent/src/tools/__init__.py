"""Tool router: maps ToolName to the callable that implements it."""

from __future__ import annotations

from typing import Any, Callable

from models import ToolName
from tools import (
    competitor_research,
    customer_feedback,
    engineering_effort,
    product_analytics,
    risk_checker,
)

TOOL_REGISTRY: dict[ToolName, Callable[..., dict[str, Any]]] = {
    ToolName.CUSTOMER_FEEDBACK_SEARCH: customer_feedback.run,
    ToolName.PRODUCT_ANALYTICS_LOOKUP: product_analytics.run,
    ToolName.COMPETITOR_RESEARCH: competitor_research.run,
    ToolName.ENGINEERING_EFFORT_ESTIMATOR: engineering_effort.run,
    ToolName.RISK_COMPLIANCE_CHECKER: risk_checker.run,
}


def execute_tool(tool_name: ToolName, tool_input: dict[str, Any]) -> dict[str, Any]:
    """Dispatch a tool call to its implementation.

    Raises tools.base.ToolExecutionError on expected failure modes; any other
    exception indicates a genuine bug and is allowed to propagate.
    """

    func = TOOL_REGISTRY[tool_name]
    return func(**tool_input)
