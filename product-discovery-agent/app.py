#!/usr/bin/env python3
"""Command-line entry point for the Product Discovery Agent.

Module 1 (single-agent, default mode - unchanged):
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
    python app.py --mode single-agent --scenario dark-mode   (equivalent to the default)

Module 2 (hub-and-spoke coordinator):
    python app.py --mode coordinator --scenario dark-mode
    python app.py --mode coordinator --scenario mobile-app
    python app.py --mode coordinator --scenario dark-mode --show-subagent-context
    python app.py --mode coordinator --scenario dark-mode --show-task-plan
    python app.py --mode coordinator --scenario dark-mode --failure-agent market_research
    python app.py --mode coordinator --scenario dark-mode --missing-context-agent technical_feasibility
    python app.py --mode coordinator --scenario dark-mode --save-trace output/coordinator-trace.json
    python app.py --mode coordinator --scenario onboarding --show-task-plan   (market_research is skipped)
    python app.py --mode coordinator --scenario unknown-feature              (all agents fail)

Live mode (real LLM + real web search via OpenRouter - requires
OPENROUTER_API_KEY in a local .env file, see .env.example):
    python app.py --mode live --scenario dark-mode
    python app.py --mode live --question "Should we add a Slack integration?"
    python app.py --mode live --question "..." --save-trace output/live-transcript.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(SRC_DIR))

from agent import DEFAULT_MAX_ITERATIONS, BugMode, ProductDiscoveryAgent, RunConfig  # noqa: E402
from coordinator.coordinator import CoordinatorRunConfig, ProductDiscoveryCoordinator  # noqa: E402
from coordinator.models import SubagentName  # noqa: E402
from models import EvidenceType  # noqa: E402

SCENARIOS: dict[str, str] = {
    "dark-mode": "Should we build dark mode?",
    "mobile-app": "Should we introduce a mobile application?",
    "ai-meeting-summary": "Should we add an AI meeting-summary feature?",
    "onboarding": "Should we improve the onboarding process?",
    "export-pdf": "Should we add an export-to-PDF feature?",
    "unknown-feature": "Should we add blockchain loyalty rewards to the platform?",
    # Coordinator-mode only: a small copy/wording change, used to demonstrate
    # that the Market Research agent is deliberately skipped (not invoked)
    # rather than always running all four subagents.
    "onboarding-copy": "Should we change the onboarding copy?",
}

DEMO_FAILURE_CHOICES = [e.value for e in EvidenceType]
SUBAGENT_CHOICES = [n.value for n in SubagentName]


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
    scenario_group.add_argument(
        "--question",
        metavar="TEXT",
        help="Provide the product question directly as an argument (any mode; most useful with --mode live).",
    )

    parser.add_argument(
        "--mode",
        choices=["single-agent", "coordinator", "live"],
        default="single-agent",
        help=(
            "single-agent (default, Module 1, offline mock), coordinator (Module 2, offline mock "
            "hub-and-spoke), or live (real LLM + real web search via OpenRouter, needs an API key)."
        ),
    )

    single_agent_group = parser.add_argument_group("single-agent mode options (Module 1)")
    single_agent_group.add_argument(
        "--bug-mode",
        choices=[m.value for m in BugMode if m != BugMode.NONE],
        default=None,
        help="Run an intentionally-broken version of the loop for educational comparison.",
    )
    single_agent_group.add_argument(
        "--demo-failure",
        choices=DEMO_FAILURE_CHOICES,
        default=None,
        help="Force the first attempt at this evidence type to fail (demonstrates retry-then-recover).",
    )
    single_agent_group.add_argument(
        "--demo-unknown-stop-reason",
        action="store_true",
        help="Force the mock model to return an unsupported stop_reason on iteration 2.",
    )
    single_agent_group.add_argument(
        "--max-iterations",
        type=int,
        default=DEFAULT_MAX_ITERATIONS,
        help=f"Cap on loop iterations (default: {DEFAULT_MAX_ITERATIONS}). Set low (e.g. 2) to demo the iteration cap.",
    )
    single_agent_group.add_argument(
        "--show-history",
        action="store_true",
        help="Print the full structured message history trace at the end of the run.",
    )

    coordinator_group = parser.add_argument_group("coordinator mode options (Module 2)")
    coordinator_group.add_argument(
        "--show-subagent-context",
        action="store_true",
        help="Print exactly what context each subagent received (and did not receive).",
    )
    coordinator_group.add_argument(
        "--show-task-plan",
        action="store_true",
        help="Print the coordinator's task decomposition plan (also shown by default; kept for explicit scripting).",
    )
    coordinator_group.add_argument(
        "--failure-agent",
        choices=SUBAGENT_CHOICES,
        default=None,
        help="Force this subagent to raise an unhandled execution failure (spec scenario 15.1).",
    )
    coordinator_group.add_argument(
        "--missing-context-agent",
        choices=["technical_feasibility"],
        default=None,
        help="Force the named agent's context package to be built without its required field (spec scenario 15.2).",
    )

    parser.add_argument(
        "--save-trace",
        metavar="PATH",
        default=None,
        help="Save the complete trace as JSON (message history in single-agent mode, event trace in coordinator mode).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress the step-by-step trace (still prints the final recommendation/brief).",
    )
    return parser


def get_question() -> str:
    print("Enter a product feature question (e.g. 'Should we build dark mode?'):")
    question = input("> ").strip()
    if not question:
        print("No question entered. Exiting.")
        sys.exit(1)
    return question


def run_single_agent(args: argparse.Namespace, question: str) -> None:
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


def run_coordinator(args: argparse.Namespace, question: str) -> None:
    failure_agent = SubagentName(args.failure_agent) if args.failure_agent else None
    missing_context_agent = SubagentName(args.missing_context_agent) if args.missing_context_agent else None

    config = CoordinatorRunConfig(
        question=question,
        failure_agent=failure_agent,
        missing_context_agent=missing_context_agent,
        show_subagent_context=args.show_subagent_context,
        show_task_plan=args.show_task_plan,
        verbose=not args.quiet,
    )

    coordinator = ProductDiscoveryCoordinator(config)
    result = coordinator.run()

    if args.save_trace:
        saved_path = result.trace.save_trace(args.save_trace)
        print(f"\nTrace saved to: {saved_path}")


def run_live(args: argparse.Namespace, question: str) -> None:
    # Imported lazily so offline modes never require `requests` or an API key.
    from live_agent import run_live_agent
    from llm.openrouter_client import OpenRouterError

    try:
        result = run_live_agent(question, verbose=not args.quiet, max_iterations=args.max_iterations)
    except OpenRouterError as exc:
        print(f"\nERROR: {exc}")
        sys.exit(1)

    if args.quiet:
        print(json.dumps(result.final_answer, indent=2))

    if args.save_trace:
        output_path = Path(args.save_trace)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result.transcript, indent=2, default=str))
        print(f"\nTranscript saved to: {output_path}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.scenario:
        question = SCENARIOS[args.scenario]
    elif args.question:
        question = args.question
    else:
        question = get_question()

    if args.mode == "coordinator":
        run_coordinator(args, question)
    elif args.mode == "live":
        run_live(args, question)
    else:
        run_single_agent(args, question)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
