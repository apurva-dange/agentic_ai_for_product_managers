"""Tool 5: Risk and Compliance Checker.

Identifies possible accessibility, privacy, security, legal, operational, or
customer-trust considerations using predefined local rules.
"""

from __future__ import annotations

from typing import Any, Optional

from data_loader import FeatureNotFoundError, get_feature_entry, load_dataset
from tools.base import ToolExecutionError

DATA_FILE = "risk_rules.json"


def run(
    feature_name: str,
    data_involved: Optional[list[str]] = None,
    user_groups_affected: Optional[list[str]] = None,
    force_failure: bool = False,
) -> dict[str, Any]:
    """Check predefined risk/compliance rules for a feature.

    Args:
        feature_name: The feature or feature description being evaluated.
        data_involved: Optional list of data types touched by the feature
            (informational context, echoed back in the response).
        user_groups_affected: Optional list of user groups affected
            (informational context, echoed back in the response).
        force_failure: Test hook that simulates a transient tool outage.

    Returns:
        A dict listing risk categories, levels, reasons, recommended
        reviews, and whether human approval is required.
    """

    if force_failure:
        raise ToolExecutionError(
            "risk_compliance_checker: transient error loading risk rule set."
        )

    dataset = load_dataset(DATA_FILE)
    try:
        entry = get_feature_entry(feature_name, dataset, DATA_FILE)
    except FeatureNotFoundError as exc:
        raise ToolExecutionError(str(exc)) from exc

    risks = entry["risks"]
    any_human_approval = any(r["human_approval_required"] for r in risks)

    return {
        "feature_queried": feature_name,
        "data_involved": data_involved or [],
        "user_groups_affected": user_groups_affected or [],
        "risks": risks,
        "human_approval_required": any_human_approval,
        "disclaimer": (
            "These are teaching-example risk flags based on predefined local "
            "rules, not a substitute for a real legal, security, or "
            "compliance review."
        ),
    }
