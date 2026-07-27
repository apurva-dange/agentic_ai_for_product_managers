"""Console output for the coordinator CLI, including the subagent-context
diagnostic view (`--show-subagent-context`) that makes context isolation
visible rather than just asserted.
"""

from __future__ import annotations

from coordinator.models import AgentResult, ContextPackage, DecisionBrief, SubagentName, TaskPlan

_RULE = "-" * 72

AGENT_DISPLAY_NAMES: dict[SubagentName, str] = {
    SubagentName.CUSTOMER_INSIGHTS: "Customer Insights Agent",
    SubagentName.MARKET_RESEARCH: "Market Research Agent",
    SubagentName.TECHNICAL_FEASIBILITY: "Technical Feasibility Agent",
    SubagentName.RISK_AND_METRICS: "Risk and Metrics Agent",
}

_DATA_ACCESS_LABEL: dict[SubagentName, str] = {
    SubagentName.CUSTOMER_INSIGHTS: "Customer feedback + product analytics data access",
    SubagentName.MARKET_RESEARCH: "Competitor research data access",
    SubagentName.TECHNICAL_FEASIBILITY: "Engineering rules data access",
    SubagentName.RISK_AND_METRICS: "Risk and compliance rules data access",
}

_ALL_DATA_ACCESS_LABELS = set(_DATA_ACCESS_LABEL.values())
_ALWAYS_EXCLUDED = ["Results from other agents", "Coordinator internal history"]


class CoordinatorEventLogger:
    """Prints a readable trace of the coordinator's run as it executes."""

    def __init__(self, verbose: bool = True) -> None:
        self.verbose = verbose

    def _print(self, text: str = "") -> None:
        if self.verbose:
            print(text)

    def log_question(self, question: str) -> None:
        self._print("=" * 72)
        self._print("PRODUCT QUESTION")
        self._print(question)
        self._print("=" * 72)

    def log_plan(self, plan: TaskPlan, force: bool = False) -> None:
        printer = print if force else self._print
        printer("\nCOORDINATOR PLAN")
        for i, task in enumerate(plan.tasks, start=1):
            printer(f"{i}. {task.objective}")
            printer(f"   reason: {task.reason}")
        for skip in plan.skipped:
            printer(f"(skipped) {AGENT_DISPLAY_NAMES[skip.agent_name]}: {skip.reason}")
        printer(_RULE)

    def log_subagent_context(self, agent_name: SubagentName, context: ContextPackage) -> None:
        # Always printed when called: this is only ever invoked because the
        # user explicitly passed --show-subagent-context, so --quiet must
        # not silently hide it.
        display_name = AGENT_DISPLAY_NAMES[agent_name]
        print(f"\n{display_name} received:")
        print(f"- Feature: {context.feature}")
        print(f"- Objective: {context.objective}")
        if context.target_users:
            print(f"- Target users: {context.target_users}")
        if context.known_problem:
            print(f"- Known customer problem: {context.known_problem}")
        if context.platforms:
            print(f"- Target platforms: {context.platforms}")
        if context.technical_constraints:
            print(f"- Technical constraints: {context.technical_constraints}")
        if context.data_involved:
            print(f"- Data types involved: {context.data_involved}")
        if context.user_groups_affected:
            print(f"- User groups affected: {context.user_groups_affected}")
        print(f"- {_DATA_ACCESS_LABEL[agent_name]}")

        print(f"{display_name} did not receive:")
        other_data_labels = sorted(_ALL_DATA_ACCESS_LABELS - {_DATA_ACCESS_LABEL[agent_name]})
        for label in other_data_labels:
            print(f"- {label.replace(' data access', ' data')}")
        for item in _ALWAYS_EXCLUDED:
            print(f"- {item}")

    def log_subagent_start(self, agent_name: SubagentName) -> None:
        self._print(f"\n{AGENT_DISPLAY_NAMES[agent_name]}: running...")

    def log_subagent_result(self, agent_name: SubagentName, result: AgentResult) -> None:
        self._print(f"{AGENT_DISPLAY_NAMES[agent_name]}: {result.status.value.upper()}")
        if result.error:
            self._print(f"  error: {result.error}")

    def log_retry(self, agent_name: SubagentName, reason: str, will_retry: bool) -> None:
        action = "retrying" if will_retry else "not retrying"
        self._print(f"  [{AGENT_DISPLAY_NAMES[agent_name]}] {action}: {reason}")

    def log_evidence_gaps(self, brief: DecisionBrief) -> None:
        self._print("\nEVIDENCE GAPS")
        if brief.evidence_gaps:
            for gap in brief.evidence_gaps:
                self._print(f"- {gap}")
        else:
            self._print("- none")
        if brief.contradictions:
            self._print("\nCONTRADICTIONS")
            for c in brief.contradictions:
                self._print(f"- {c}")

    def log_final(self, brief: DecisionBrief) -> None:
        # Always shown, even in --quiet mode: the brief is the deliverable.
        print("\nFINAL RECOMMENDATION")
        print(brief.recommendation)
        print("\nCONFIDENCE")
        print(brief.confidence)
        print("\n" + "=" * 72)
        print("FULL DECISION BRIEF (JSON)")
        print("=" * 72)
        print(brief.model_dump_json(indent=2))
