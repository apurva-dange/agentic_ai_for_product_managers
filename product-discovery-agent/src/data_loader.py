"""Loads synthetic JSON datasets and resolves free-text feature names.

Centralizing this here keeps every tool's "which feature is the user asking
about" logic identical, and keeps file I/O out of the tool modules themselves.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class FeatureNotFoundError(Exception):
    """Raised when a feature name cannot be matched to any known dataset entry."""


@lru_cache(maxsize=None)
def _load_json(filename: str) -> dict[str, Any]:
    path = DATA_DIR / filename
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_dataset(filename: str) -> dict[str, Any]:
    """Load (and cache) one of the synthetic JSON data files by name."""

    return _load_json(filename)


def resolve_feature_key(feature_name: str, dataset: dict[str, Any]) -> Optional[str]:
    """Match a free-text feature name against a dataset's canonical keys/aliases.

    Matching is intentionally simple (case-insensitive substring matching
    against known aliases) since this is a teaching demo with a small, fixed
    set of features rather than a production entity-resolution system.
    """

    normalized = feature_name.strip().lower().replace("-", " ")
    features = dataset.get("features", {})

    if normalized in features:
        return normalized

    for key, entry in features.items():
        aliases = [a.lower() for a in entry.get("aliases", [])] + [key.replace("_", " ")]
        for alias in aliases:
            if alias == normalized or alias in normalized or normalized in alias:
                return key
    return None


def get_feature_entry(feature_name: str, dataset: dict[str, Any], filename: str) -> dict[str, Any]:
    """Resolve a feature name to its dataset entry, or raise FeatureNotFoundError."""

    key = resolve_feature_key(feature_name, dataset)
    if key is None:
        raise FeatureNotFoundError(
            f"No synthetic data found for feature '{feature_name}' in {filename}."
        )
    return dataset["features"][key]
