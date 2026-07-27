"""Tests for failure handling, iteration caps, insufficient evidence, bug
modes, and a basic sensitive-data scan (requirements 8, 9, 10, 17, 18, 19)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from agent import BugMode, ProductDiscoveryAgent, RunConfig
from models import EvidenceType, MessageRole, ToolStatus

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_tool_failure_is_recorded_and_retried_then_recovers() -> None:
    """Scenario 3: a transient failure is recorded, then a retry succeeds."""

    config = RunConfig(
        question="Should we build dark mode?",
        verbose=False,
        demo_failure_target=EvidenceType.COMPETITOR_RESEARCH,
    )
    result = ProductDiscoveryAgent(config).run()

    tool_results = [e for e in result.history.entries if e.role == MessageRole.TOOL_RESULT]
    failure_entries = [e for e in tool_results if e.status == ToolStatus.FAILURE]
    success_entries = [e for e in tool_results if e.status == ToolStatus.SUCCESS]

    assert len(failure_entries) == 1
    assert EvidenceType.COMPETITOR_RESEARCH in result.evidence_plan.collected
    assert result.stop_reason == "end_turn"
    assert len(success_entries) == 5


def test_max_iterations_reached_stops_without_infinite_loop() -> None:
    """Scenario 5: the loop must stop at the iteration cap."""

    config = RunConfig(question="Should we build dark mode?", verbose=False, max_iterations=2)
    result = ProductDiscoveryAgent(config).run()

    assert result.stop_reason == "max_iterations_reached"
    assert result.iterations_used == 2
    assert not result.evidence_plan.is_complete()


def test_insufficient_evidence_for_unrecognized_feature() -> None:
    """Scenario 6: data does not support a confident recommendation."""

    config = RunConfig(
        question="Should we add blockchain loyalty rewards?",
        verbose=False,
        max_iterations=10,
    )
    result = ProductDiscoveryAgent(config).run()

    assert result.recommendation.recommendation == "Insufficient evidence"
    assert result.recommendation.confidence == "Low"
    assert result.evidence_plan.collected == []


def test_bug_mode_skip_tool_history_prevents_progress() -> None:
    """Bug mode 1: tool results never enter history/evidence state, so the
    agent cannot complete the task and repeats the same request."""

    config = RunConfig(
        question="Should we build dark mode?",
        verbose=False,
        bug_mode=BugMode.SKIP_TOOL_HISTORY,
        max_iterations=4,
    )
    result = ProductDiscoveryAgent(config).run()

    tool_result_entries = [e for e in result.history.entries if e.role == MessageRole.TOOL_RESULT]
    assert len(tool_result_entries) == 0
    assert result.evidence_plan.collected == []
    assert result.stop_reason == "max_iterations_reached"
    assert result.recommendation.recommendation == "Insufficient evidence"


def test_bug_mode_end_too_early_produces_incomplete_answer() -> None:
    """Bug mode 2: the loop exits after the first tool call instead of
    continuing, producing an incomplete recommendation."""

    config = RunConfig(
        question="Should we build dark mode?",
        verbose=False,
        bug_mode=BugMode.END_TOO_EARLY,
    )
    result = ProductDiscoveryAgent(config).run()

    assert result.stop_reason == "bug_mode_end_too_early"
    assert result.iterations_used == 1
    assert len(result.evidence_plan.collected) == 1
    assert not result.evidence_plan.is_complete()
    assert result.recommendation.confidence == "Low"


SECRET_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9]{10,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),  # SSN-shaped pattern
    re.compile(r"password\s*=\s*['\"][^'\"]+['\"]", re.IGNORECASE),
]


def test_no_secrets_or_ssn_like_patterns_in_source_or_data() -> None:
    """Requirement 19: scan for accidental secrets or sensitive-data patterns."""

    scanned_files = list((PROJECT_ROOT / "src").rglob("*.py"))
    scanned_files += list((PROJECT_ROOT / "data").rglob("*.json"))
    scanned_files.append(PROJECT_ROOT / "app.py")

    offenders = []
    for path in scanned_files:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                offenders.append((str(path), pattern.pattern))

    assert offenders == []


def test_all_synthetic_data_files_declare_synthetic_flag() -> None:
    """Every mock data file must clearly label itself as synthetic demo data."""

    for filename in [
        "customer_feedback.json",
        "product_analytics.json",
        "competitors.json",
        "engineering_rules.json",
        "risk_rules.json",
    ]:
        data = json.loads((PROJECT_ROOT / "data" / filename).read_text())
        assert data["_meta"]["synthetic"] is True
