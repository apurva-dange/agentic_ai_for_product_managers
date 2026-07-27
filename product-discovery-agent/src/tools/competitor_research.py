"""Tool 3: Competitor Research.

Searches synthetic competitor data. All competitor names and details are
fictional and clearly labelled as synthetic demo data.
"""

from __future__ import annotations

from typing import Any, Optional

from data_loader import FeatureNotFoundError, get_feature_entry, load_dataset
from tools.base import ToolExecutionError

DATA_FILE = "competitors.json"


def run(
    feature_name: str,
    competitor_category: Optional[str] = None,
    force_failure: bool = False,
) -> dict[str, Any]:
    """Look up synthetic competitor data for a feature.

    Args:
        feature_name: The feature being evaluated.
        competitor_category: Optional filter (e.g. "productivity_saas").
        force_failure: Test hook that simulates a transient tool outage.

    Returns:
        A dict describing which fictional competitors offer the feature,
        which do not, how it's implemented, and differentiation opportunities.
    """

    if force_failure:
        raise ToolExecutionError(
            "competitor_research: transient error reaching competitor research index."
        )

    dataset = load_dataset(DATA_FILE)
    try:
        entry = get_feature_entry(feature_name, dataset, DATA_FILE)
    except FeatureNotFoundError as exc:
        raise ToolExecutionError(str(exc)) from exc

    if competitor_category and competitor_category.lower() != entry["category"].lower():
        note = (
            f"No synthetic competitor data tagged for category "
            f"'{competitor_category}'; showing all tracked competitors instead."
        )
    else:
        note = None

    return {
        "feature_queried": feature_name,
        "competitor_category": entry["category"],
        "category_filter_note": note,
        "competitors_offering": entry["offer"],
        "competitors_not_offering": entry["do_not_offer"],
        "differentiation_opportunities": entry["differentiation_opportunities"],
        "source_references": entry["source_references"],
        "synthetic_data": True,
        "disclaimer": "All competitor names and details are fictional synthetic demo data.",
    }
