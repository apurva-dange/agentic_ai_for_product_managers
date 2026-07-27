"""Tool 4: Engineering Effort Estimator.

Estimates implementation effort using predefined local rules. Estimates are
relative (Low/Medium/High/Unknown) teaching examples, never precise
production commitments.
"""

from __future__ import annotations

from typing import Any, Optional

from data_loader import FeatureNotFoundError, get_feature_entry, load_dataset
from tools.base import ToolExecutionError

DATA_FILE = "engineering_rules.json"


def run(
    feature_name: str,
    platforms: Optional[list[str]] = None,
    technical_dependencies: Optional[list[str]] = None,
    force_failure: bool = False,
) -> dict[str, Any]:
    """Estimate relative engineering effort for a feature using local rules.

    Args:
        feature_name: The feature being evaluated.
        platforms: Optional list of affected platforms (e.g. ["web", "ios"]).
        technical_dependencies: Optional list of dependencies the caller
            already knows about, merged into the returned dependency list.
        force_failure: Test hook that simulates a transient tool outage.

    Returns:
        A dict with effort level, expected work, dependencies, risks,
        testing requirements, and a confidence level for the estimate.
    """

    if force_failure:
        raise ToolExecutionError(
            "engineering_effort_estimator: transient error loading estimation rules."
        )

    dataset = load_dataset(DATA_FILE)
    try:
        entry = get_feature_entry(feature_name, dataset, DATA_FILE)
    except FeatureNotFoundError as exc:
        raise ToolExecutionError(str(exc)) from exc

    dependencies = list(entry["dependencies"])
    for dep in technical_dependencies or []:
        if dep not in dependencies:
            dependencies.append(dep)

    return {
        "feature_queried": feature_name,
        "platforms_considered": platforms or ["unspecified"],
        "estimated_effort_level": entry["effort_level"],
        "expected_engineering_work": entry["expected_work"],
        "dependencies": dependencies,
        "risks": entry["risks"],
        "testing_requirements": entry["testing_requirements"],
        "confidence_level": entry["confidence"],
        "platforms_note": entry["platforms_note"],
        "disclaimer": (
            "This is a relative, teaching-purpose estimate based on predefined "
            "local rules, not a real engineering commitment."
        ),
    }
