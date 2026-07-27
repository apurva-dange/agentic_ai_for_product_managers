#!/usr/bin/env python3
"""Local simulated evaluation harness for the Module 2 coordinator.

IMPORTANT: every number this script prints is a LOCAL SIMULATED EVALUATION
RESULT, produced by running the deterministic mock coordinator against
synthetic product questions and synthetic data. It is a teaching-purpose
sanity check on the implementation's own behavior, not a measurement of any
real product outcome, business impact, or model quality.

Usage:
    python evaluate.py
"""

from __future__ import annotations

import contextlib
import io
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

SRC_DIR = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(SRC_DIR))

from coordinator.coordinator import CoordinatorRunConfig, ProductDiscoveryCoordinator  # noqa: E402
from coordinator.models import AgentStatus, DecisionBrief, SubagentName  # noqa: E402
from pydantic import ValidationError  # noqa: E402

UNSUPPORTED_CLAIM_PHRASES = [
    "guaranteed",
    "100% certain",
    "will definitely increase",
    "proven to increase revenue",
    "will increase revenue",
    "will boost conversion",
    "no risk",
]


@dataclass
class EvalCase:
    case_id: str
    question: str
    failure_agent: Optional[SubagentName] = None
    missing_context_agent: Optional[SubagentName] = None
    expect_skipped: set[SubagentName] = field(default_factory=set)
    expect_all_invoked: bool = True
    expect_failure_scenario: bool = False
    expect_insufficient_evidence: bool = False


CASES: list[EvalCase] = [
    EvalCase("case-01", "Should we build dark mode?"),
    EvalCase("case-02", "Should we introduce a mobile application?"),
    EvalCase("case-03", "Should we add an AI meeting-summary feature?"),
    EvalCase("case-04", "Should we improve the onboarding process?"),
    EvalCase("case-05", "Should we add an export-to-PDF feature?"),
    EvalCase(
        "case-06", "Should we change the onboarding copy?",
        expect_skipped={SubagentName.MARKET_RESEARCH}, expect_all_invoked=False,
    ),
    EvalCase(
        "case-07", "Should we improve the dark mode toggle wording?",
        expect_skipped={SubagentName.MARKET_RESEARCH}, expect_all_invoked=False,
    ),
    EvalCase(
        "case-08", "Should we add blockchain loyalty rewards?",
        expect_insufficient_evidence=True, expect_failure_scenario=True, expect_all_invoked=False,
    ),
    EvalCase(
        "case-09", "Should we build dark mode?",
        failure_agent=SubagentName.MARKET_RESEARCH, expect_failure_scenario=True,
    ),
    EvalCase(
        "case-10", "Should we build dark mode?",
        missing_context_agent=SubagentName.TECHNICAL_FEASIBILITY, expect_failure_scenario=True,
    ),
    EvalCase(
        "case-11", "Should we introduce a mobile application?",
        failure_agent=SubagentName.TECHNICAL_FEASIBILITY, expect_failure_scenario=True,
    ),
    EvalCase("case-12", "Should we add an AI meeting-summary feature?"),
]


@dataclass
class CaseReport:
    case_id: str
    question: str
    schema_valid: bool
    agent_selection_correct: bool
    failure_handled_correctly: Optional[bool]
    evidence_gaps_present: bool
    success_metrics_present: bool
    unsupported_claims_found: list[str]
    recommendation: str
    confidence: str


def _validate_schema(brief: DecisionBrief) -> bool:
    try:
        DecisionBrief.model_validate_json(brief.model_dump_json())
        return True
    except ValidationError:
        return False


def _agent_selection_correct(case: EvalCase, results: dict[SubagentName, object]) -> bool:
    actually_skipped = {name for name, r in results.items() if r.status == AgentStatus.SKIPPED}
    if case.expect_all_invoked:
        return actually_skipped == set()
    return case.expect_skipped.issubset(actually_skipped)


def _failure_handled_correctly(case: EvalCase, brief: DecisionBrief) -> bool:
    if case.expect_insufficient_evidence:
        return brief.recommendation == "Insufficient evidence" and brief.human_decision_required is True
    if case.failure_agent is not None:
        return case.failure_agent.value in brief.failed_agents and brief.confidence in ("Low", "Medium")
    if case.missing_context_agent is not None:
        # The expected outcome here is a *successful* recovery: the
        # coordinator detects the missing field and supplies a safe
        # fallback, so the agent should not end up in failed_agents.
        return case.missing_context_agent.value not in brief.failed_agents
    return True


def _evidence_gaps_expected(case: EvalCase) -> bool:
    """Only an unresolved failure should leave a lasting evidence gap - a
    successfully-recovered missing-context case is expected to have none."""

    return case.failure_agent is not None or case.expect_insufficient_evidence


def _find_unsupported_claims(brief: DecisionBrief) -> list[str]:
    text = brief.model_dump_json().lower()
    return [phrase for phrase in UNSUPPORTED_CLAIM_PHRASES if phrase in text]


def run_case(case: EvalCase) -> CaseReport:
    config = CoordinatorRunConfig(
        question=case.question,
        failure_agent=case.failure_agent,
        missing_context_agent=case.missing_context_agent,
        verbose=False,
    )
    # The coordinator always prints its final brief (by design, for CLI use)
    # regardless of verbose - silence that here so the eval summary stays readable.
    with contextlib.redirect_stdout(io.StringIO()):
        result = ProductDiscoveryCoordinator(config).run()
    brief = result.brief

    success_metrics_present = bool(brief.risk_and_metrics.model_extra.get("success_metrics"))
    if brief.risk_and_metrics.status in ("failed", "skipped"):
        success_metrics_present = True  # not applicable; don't penalize an intentionally-absent section

    return CaseReport(
        case_id=case.case_id,
        question=case.question,
        schema_valid=_validate_schema(brief),
        agent_selection_correct=_agent_selection_correct(case, result.results),
        failure_handled_correctly=(
            _failure_handled_correctly(case, brief) if case.expect_failure_scenario else None
        ),
        evidence_gaps_present=(bool(brief.evidence_gaps) if _evidence_gaps_expected(case) else True),
        success_metrics_present=success_metrics_present,
        unsupported_claims_found=_find_unsupported_claims(brief),
        recommendation=brief.recommendation,
        confidence=brief.confidence,
    )


def main() -> int:
    print("=" * 72)
    print("LOCAL SIMULATED EVALUATION RESULTS")
    print("(synthetic questions, synthetic data, deterministic mock coordinator -")
    print(" this does not measure real product outcomes)")
    print("=" * 72)

    reports = [run_case(case) for case in CASES]

    total = len(reports)
    valid_schema = sum(r.schema_valid for r in reports)
    correct_selection = sum(r.agent_selection_correct for r in reports)
    failure_cases = [r for r in reports if r.failure_handled_correctly is not None]
    failure_correct = sum(bool(r.failure_handled_correctly) for r in failure_cases)
    gaps_ok = sum(r.evidence_gaps_present for r in reports)
    metrics_ok = sum(r.success_metrics_present for r in reports)
    total_unsupported_claims = sum(len(r.unsupported_claims_found) for r in reports)

    print(f"\nCases evaluated: {total}")
    print(f"Valid structured outputs: {valid_schema}/{total}")
    print(f"Appropriate agent selection: {correct_selection}/{total}")
    print(f"Failure scenarios handled correctly: {failure_correct}/{len(failure_cases)}")
    print(f"Evidence gaps identified where expected: {gaps_ok}/{total}")
    print(f"Cases with success metrics present (where applicable): {metrics_ok}/{total}")
    print(f"Unsupported evidence claims detected: {total_unsupported_claims}")

    print("\nPer-case detail:")
    for r in reports:
        flags = []
        if not r.schema_valid:
            flags.append("SCHEMA_INVALID")
        if not r.agent_selection_correct:
            flags.append("AGENT_SELECTION_WRONG")
        if r.failure_handled_correctly is False:
            flags.append("FAILURE_NOT_HANDLED")
        if not r.evidence_gaps_present:
            flags.append("MISSING_EVIDENCE_GAP_NOTE")
        if not r.success_metrics_present:
            flags.append("MISSING_SUCCESS_METRICS")
        if r.unsupported_claims_found:
            flags.append(f"UNSUPPORTED_CLAIMS={r.unsupported_claims_found}")
        status = "OK" if not flags else "FLAGGED: " + ", ".join(flags)
        print(f"  {r.case_id}: '{r.question}' -> {r.recommendation} / {r.confidence} [{status}]")

    print("\nAll results above are LOCAL SIMULATED EVALUATION RESULTS on synthetic data.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
