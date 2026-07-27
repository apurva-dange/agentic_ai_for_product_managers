#!/usr/bin/env python3
"""Command-line entry point for the Product Discovery Agent.

Examples:
    python app.py --scenario dark-mode
    python app.py --scenario onboarding --show-history
    python app.py --scenario dark-mode --save-trace output/trace.json
    python app.py --interactive
    python app.py --scenario dark-mode --demo-failure competitor_research
    python app.py --scenario dark-mode --demo-unknown-stop-reason
    python app.py --scenario dark-mode --max-iterations 2
    python app.py --scenario unknown-feature
    python app.py --scenario dark-mode --bug-mode skip-tool-history
    python app.py --scenario dark-mode --bug-mode end-too-early
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(SRC_DIR))

from agent import DEFAULT_MAX_ITERATIONS, BugMode, ProductDiscoveryAgent, RunConfig  # noqa: E402
from models import EvidenceType  # noqa: E402

SCENARIOS: dict[str, str] = {
    "dark-mode": "Should we build dark mode?",
    "mobile-app": "Should we introduce a mobile application?",
    "ai-meeting-summary": "Should we add an AI meeting-summary feature?",
    "onboarding": "Should we improve the onboarding process?",
    "export-pdf": "Should we add an export-to-PDF feature?",
    "unknown-feature": "Should we add blockchain loyalty rewards to the platform?",
}

DEMO_FAILURE_CHOICES = [e.value for e in EvidenceType]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Product Discovery Agent - an explainable agentic loop for product feature evaluation.",
    )
    scenario_group = parser.add_mutually_exclusive_group(required=True)
    scenario_group.add_argument(
        "--scenario",
        choices=sorted(SCENARIOS.keys()),
        help="Run one of the built-in demo scenarios.",
    )
    scenario_group.add_argument(
        "--interactive",
        action="store_true",
        help="Prompt for a free-text product question instead of a preset scenario.",
    )

    parser.add_argument(
        "--bug-mode",
        choices=[m.value for m in BugMode if m != BugMode.NONE],
        default=None,
        help="Run an intentionally-broken version of the loop for educational comparison.",
    )
    parser.add_argument(
        "--demo-failure",
        choices=DEMO_FAILURE_CHOICES,
        default=None,
        help="Force the first attempt at this evidence type to fail (demonstrates retry-then-recover).",
    )
    parser.add_argument(
        "--demo-unknown-stop-reason",
        action="store_true",
        help="Force the mock model to return an unsupported stop_reason on iteration 2.",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=DEFAULT_MAX_ITERATIONS,
        help=f"Cap on loop iterations (default: {DEFAULT_MAX_ITERATIONS}). Set low (e.g. 2) to demo the iteration cap.",
    )
    parser.add_argument(
        "--show-history",
        action="store_true",
        help="Print the full structured message history trace at the end of the run.",
    )
    parser.add_argument(
        "--save-trace",
        metavar="PATH",
        default=None,
        help="Save the complete message history trace as JSON to this path.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress the step-by-step loop trace (still prints the final recommendation).",
    )
    return parser


def get_question() -> str:
    print("Enter a product feature question (e.g. 'Should we build dark mode?'):")
    question = input("> ").strip()
    if not question:
        print("No question entered. Exiting.")
        sys.exit(1)
    return question


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    question = SCENARIOS[args.scenario] if args.scenario else get_question()

    demo_failure_target = EvidenceType(args.demo_failure) if args.demo_failure else None
    bug_mode = BugMode(args.bug_mode) if args.bug_mode else BugMode.NONE
    force_unknown_stop_at = 2 if args.demo_unknown_stop_reason else None

    config = RunConfig(
        question=question,
        max_iterations=args.max_iterations,
        bug_mode=bug_mode,
        demo_failure_target=demo_failure_target,
        force_unknown_stop_at_iteration=force_unknown_stop_at,
        verbose=not args.quiet,
    )

    agent = ProductDiscoveryAgent(config)
    result = agent.run()

    if args.show_history:
        print()
        print(result.history.render_trace())

    if args.save_trace:
        saved_path = result.history.save_trace(args.save_trace)
        print(f"\nTrace saved to: {saved_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
