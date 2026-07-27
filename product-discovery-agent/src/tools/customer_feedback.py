"""Tool 1: Customer Feedback Search.

Searches synthetic customer-feedback records for requests related to a
proposed feature.
"""

from __future__ import annotations

from typing import Any, Optional

from data_loader import FeatureNotFoundError, get_feature_entry, load_dataset
from tools.base import ToolExecutionError

DATA_FILE = "customer_feedback.json"


def run(
    feature_name: str,
    customer_segment: Optional[str] = None,
    force_failure: bool = False,
) -> dict[str, Any]:
    """Search synthetic customer feedback for a feature.

    Args:
        feature_name: The feature the product manager is evaluating.
        customer_segment: Optional filter (e.g. "enterprise", "smb", "individual").
        force_failure: Test hook that simulates a transient tool outage.

    Returns:
        A dict with total matches, representative comments, segment
        frequency, related pain points, and source record IDs.
    """

    if force_failure:
        raise ToolExecutionError(
            "customer_feedback_search: transient error contacting feedback index."
        )

    dataset = load_dataset(DATA_FILE)
    try:
        entry = get_feature_entry(feature_name, dataset, DATA_FILE)
    except FeatureNotFoundError as exc:
        raise ToolExecutionError(str(exc)) from exc

    records = entry["records"]
    if customer_segment:
        segment_norm = customer_segment.strip().lower()
        records = [r for r in records if r["segment"] == segment_norm]

    pain_points = sorted({r["pain_point"] for r in records})
    segments_present = sorted({r["segment"] for r in records})

    return {
        "feature_queried": feature_name,
        "segment_filter": customer_segment,
        "total_matching_requests": entry["total_matching_requests"],
        "returned_record_count": len(records),
        "representative_comments": [
            {"id": r["id"], "segment": r["segment"], "comment": r["comment"]}
            for r in records[:5]
        ],
        "customer_segments": segments_present,
        "frequency_by_segment": entry["segment_frequency"],
        "related_pain_points": pain_points,
        "source_record_ids": [r["id"] for r in records],
        "synthetic_data": True,
    }
