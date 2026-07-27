"""Tool 2: Product Analytics Lookup.

Searches synthetic product-usage data for behavioral evidence related to a
feature. Always surfaces data limitations so the agent (and the reader)
does not overstate what the data proves.
"""

from __future__ import annotations

from typing import Any, Optional

from data_loader import FeatureNotFoundError, get_feature_entry, load_dataset
from tools.base import ToolExecutionError

DATA_FILE = "product_analytics.json"


def run(
    feature_name: str,
    metric: Optional[str] = None,
    force_failure: bool = False,
) -> dict[str, Any]:
    """Look up synthetic usage analytics related to a feature.

    Args:
        feature_name: The feature or product area to look up.
        metric: Optional metric of interest (currently informational only;
            all relevant metrics for the feature area are returned).
        force_failure: Test hook that simulates a transient tool outage.

    Returns:
        A dict with usage patterns, drop-off rates, session info,
        accessibility signals, trends, and explicit data limitations.
    """

    if force_failure:
        raise ToolExecutionError(
            "product_analytics_lookup: transient error querying analytics warehouse."
        )

    dataset = load_dataset(DATA_FILE)
    try:
        entry = get_feature_entry(feature_name, dataset, DATA_FILE)
    except FeatureNotFoundError as exc:
        raise ToolExecutionError(str(exc)) from exc

    return {
        "feature_queried": feature_name,
        "metric_requested": metric,
        "metric_area": entry["metric_area"],
        "usage_patterns": entry["usage_patterns"],
        "drop_off_rates": entry["drop_off_rates"],
        "session_info": entry["session_info"],
        "accessibility_signals": entry["accessibility_signals"],
        "trends": entry["trends"],
        "data_limitations": entry["data_limitations"],
        "synthetic_data": True,
    }
