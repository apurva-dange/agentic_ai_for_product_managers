"""Combines validated subagent results into one coherent decision brief.

This is a deliberately simple, explainable, rule-based heuristic (matching
Module 1's recommendation logic in spirit) - not a statistically calibrated
confidence model. It never averages away a critical failure: if a critical
agent (customer insights or technical feasibility) failed, the brief is
capped at "Investigate further" / "Low" no matter how the other signals look.
"""

from __future__ import annotations

from coordinator.models import (
    AgentResult,
    AgentStatus,
    DecisionBrief,
    ExperimentProposal,
    SubagentBriefSection,
    SubagentName,
    TaskPlan,
)

AGENT_LABELS: dict[SubagentName, str] = {
    SubagentName.CUSTOMER_INSIGHTS: "Customer Insights",
    SubagentName.MARKET_RESEARCH: "Market Research",
    SubagentName.TECHNICAL_FEASIBILITY: "Technical Feasibility",
    SubagentName.RISK_AND_METRICS: "Risk and Metrics",
}

CRITICAL_AGENTS = {SubagentName.CUSTOMER_INSIGHTS, SubagentName.TECHNICAL_FEASIBILITY}

EFFORT_PENALTY = {"Low": 0, "Medium": -1, "High": -2, "Unknown": -1}
STRENGTH_SCORE = {"high": 2, "medium": 1, "low": 0, "unknown": 0}


class ResultAggregator:
    """Turns a dict of validated AgentResults into a DecisionBrief."""

    def aggregate(
        self,
        feature_display_name: str,
        decision_question: str,
        results: dict[SubagentName, AgentResult],
        plan: TaskPlan,
    ) -> DecisionBrief:
        successful = {n: r for n, r in results.items() if r.status == AgentStatus.SUCCESS}
        partial = {n: r for n, r in results.items() if r.status == AgentStatus.PARTIAL}
        failed = {n: r for n, r in results.items() if r.status == AgentStatus.FAILED}
        skipped = {n: r for n, r in results.items() if r.status == AgentStatus.SKIPPED}

        evidence_gaps = self._evidence_gaps(failed, partial, skipped)
        contradictions = self._detect_contradictions(results)

        critical_failed = any(name in CRITICAL_AGENTS for name in failed)
        usable = {**successful, **partial}

        if not usable:
            recommendation = "Insufficient evidence"
            confidence = "Low"
        elif critical_failed:
            recommendation = "Investigate further"
            confidence = "Low"
        else:
            score = self._score(usable)
            recommendation = self._recommendation_from_score(score)
            confidence = self._confidence(successful, partial, failed, contradictions)
            if contradictions and recommendation in ("Build now", "Add to roadmap"):
                recommendation = "Run an experiment"

        assumptions = self._assumptions(usable)
        next_steps = self._next_steps(usable, failed, recommendation)
        experiment_proposal = self._experiment_proposal(feature_display_name, usable)

        return DecisionBrief(
            feature=feature_display_name,
            decision_question=decision_question,
            recommendation=recommendation,
            confidence=confidence,
            executive_summary=self._executive_summary(
                feature_display_name, recommendation, usable, failed, contradictions
            ),
            customer_insights=self._section(results.get(SubagentName.CUSTOMER_INSIGHTS)),
            market_research=self._section(results.get(SubagentName.MARKET_RESEARCH)),
            technical_feasibility=self._section(results.get(SubagentName.TECHNICAL_FEASIBILITY)),
            risk_and_metrics=self._section(results.get(SubagentName.RISK_AND_METRICS)),
            evidence_gaps=evidence_gaps,
            contradictions=contradictions,
            assumptions=assumptions,
            recommended_next_steps=next_steps,
            experiment_proposal=experiment_proposal,
            failed_agents=[name.value for name in failed],
            human_decision_required=True,
        )

    # -- scoring -----------------------------------------------------------

    def _score(self, usable: dict[SubagentName, AgentResult]) -> int:
        score = 0
        customer = usable.get(SubagentName.CUSTOMER_INSIGHTS)
        market = usable.get(SubagentName.MARKET_RESEARCH)
        technical = usable.get(SubagentName.TECHNICAL_FEASIBILITY)
        risk = usable.get(SubagentName.RISK_AND_METRICS)

        if customer:
            score += STRENGTH_SCORE.get(customer.data.get("demand_strength", "unknown"), 0)
        if market:
            score += STRENGTH_SCORE.get(market.data.get("market_expectation", "unknown"), 0) // 2
        if technical:
            score += EFFORT_PENALTY.get(technical.data.get("effort", "Unknown"), -1)
        if risk:
            risk_levels = {r["level"] for r in risk.data.get("risks", [])}
            if "High" in risk_levels:
                score -= 2
            elif "Medium" in risk_levels:
                score -= 1
        return score

    def _recommendation_from_score(self, score: int) -> str:
        if score >= 3:
            return "Build now"
        if score >= 1:
            return "Add to roadmap"
        if score == 0:
            return "Run an experiment"
        if score >= -2:
            return "Investigate further"
        return "Do not prioritize"

    def _confidence(
        self,
        successful: dict[SubagentName, AgentResult],
        partial: dict[SubagentName, AgentResult],
        failed: dict[SubagentName, AgentResult],
        contradictions: list[str],
    ) -> str:
        if contradictions:
            return "Low" if (partial or failed) else "Medium"
        if failed:
            return "Low"
        if partial:
            return "Medium"
        return "High" if successful else "Low"

    # -- gap and contradiction detection ------------------------------------

    def _evidence_gaps(
        self,
        failed: dict[SubagentName, AgentResult],
        partial: dict[SubagentName, AgentResult],
        skipped: dict[SubagentName, AgentResult],
    ) -> list[str]:
        gaps: list[str] = []
        for name, result in failed.items():
            gaps.append(f"{AGENT_LABELS[name]} unavailable: {result.error or 'execution failed'}")
        for name, result in partial.items():
            for item in result.missing_information:
                gaps.append(f"{AGENT_LABELS[name]}: missing {item}")
        for name, result in skipped.items():
            gaps.append(f"{AGENT_LABELS[name]} skipped: {result.summary}")
        return gaps

    def _detect_contradictions(self, results: dict[SubagentName, AgentResult]) -> list[str]:
        contradictions: list[str] = []

        def usable_data(name: SubagentName) -> dict:
            result = results.get(name)
            if result and result.status in (AgentStatus.SUCCESS, AgentStatus.PARTIAL):
                return result.data
            return {}

        customer_data = usable_data(SubagentName.CUSTOMER_INSIGHTS)
        technical_data = usable_data(SubagentName.TECHNICAL_FEASIBILITY)
        market_data = usable_data(SubagentName.MARKET_RESEARCH)

        demand = customer_data.get("demand_strength")
        effort = technical_data.get("effort")
        market_expectation = market_data.get("market_expectation")

        if demand == "high" and effort == "High":
            contradictions.append(
                "Strong customer demand exists, but estimated engineering effort is high - "
                "the cost/benefit trade-off should be validated before committing."
            )
        if demand == "high" and market_expectation == "low":
            contradictions.append(
                "Customers are requesting this feature, but it does not yet appear to be a "
                "broad market expectation - consider whether this is a niche vs. mainstream need."
            )
        if demand in ("low", None) and effort == "High":
            contradictions.append(
                "Estimated engineering effort is high while customer demand evidence is weak "
                "or unavailable - this combination warrants extra scrutiny before investment."
            )
        return contradictions

    # -- narrative fields ----------------------------------------------------

    def _assumptions(self, usable: dict[SubagentName, AgentResult]) -> list[str]:
        assumptions: list[str] = []
        customer = usable.get(SubagentName.CUSTOMER_INSIGHTS)
        if customer:
            assumptions.append("Assumes the synthetic customer requests reviewed are representative of broader demand.")
        technical = usable.get(SubagentName.TECHNICAL_FEASIBILITY)
        if technical:
            assumptions.extend(technical.data.get("assumptions", []))
        return assumptions

    def _next_steps(
        self,
        usable: dict[SubagentName, AgentResult],
        failed: dict[SubagentName, AgentResult],
        recommendation: str,
    ) -> list[str]:
        steps: list[str] = []
        risk = usable.get(SubagentName.RISK_AND_METRICS)
        if risk:
            steps.extend(f"Review: {review}" for review in risk.data.get("required_reviews", []))
        if failed:
            steps.append(
                "Re-run the analysis for the failed area(s) once that evidence source is available."
            )
        if recommendation in ("Run an experiment", "Investigate further"):
            steps.append("Validate open questions with a small, time-boxed experiment before full investment.")
        if not steps:
            steps.append("Confirm findings with a human product manager before acting on this brief.")
        return steps

    def _experiment_proposal(
        self, feature_display_name: str, usable: dict[SubagentName, AgentResult]
    ) -> ExperimentProposal:
        customer = usable.get(SubagentName.CUSTOMER_INSIGHTS)
        risk = usable.get(SubagentName.RISK_AND_METRICS)
        target_users = customer.data.get("customer_segments", []) if customer else []
        success_metrics = risk.data.get("success_metrics", []) if risk else []
        return ExperimentProposal(
            objective=f"Validate whether '{feature_display_name}' delivers the expected value before a full build commitment.",
            target_users=target_users,
            success_metrics=success_metrics[:3],
            decision_rule=(
                "Proceed to a full build if the proposed success metrics trend positively "
                "during the experiment window; otherwise re-evaluate."
            ),
        )

    def _executive_summary(
        self,
        feature_display_name: str,
        recommendation: str,
        usable: dict[SubagentName, AgentResult],
        failed: dict[SubagentName, AgentResult],
        contradictions: list[str],
    ) -> str:
        if recommendation == "Insufficient evidence":
            return (
                f"No reliable evidence could be gathered for '{feature_display_name}'. "
                "A human product manager should investigate manually before any decision is made."
            )

        parts = []
        customer = usable.get(SubagentName.CUSTOMER_INSIGHTS)
        if customer:
            parts.append(f"customer demand is {customer.data.get('demand_strength', 'unknown')}")
        market = usable.get(SubagentName.MARKET_RESEARCH)
        if market:
            parts.append(f"market expectation is {market.data.get('market_expectation', 'unknown')}")
        technical = usable.get(SubagentName.TECHNICAL_FEASIBILITY)
        if technical:
            parts.append(f"estimated engineering effort is {technical.data.get('effort', 'Unknown').lower()}")
        risk = usable.get(SubagentName.RISK_AND_METRICS)
        if risk and risk.data.get("risks"):
            levels = sorted({r["level"] for r in risk.data["risks"]})
            parts.append(f"identified risk levels include {', '.join(levels)}")

        summary = f"For '{feature_display_name}': " + "; ".join(parts) + "." if parts else (
            f"For '{feature_display_name}', only partial evidence was available."
        )
        if failed:
            summary += f" {len(failed)} specialist area(s) could not be evaluated and are called out below."
        if contradictions:
            summary += " The evidence includes a trade-off that should be weighed explicitly, not averaged away."
        summary += f" Suggested next step: {recommendation.lower()}."
        return summary

    def _section(self, result: AgentResult | None) -> SubagentBriefSection:
        if result is None:
            return SubagentBriefSection(status="skipped", summary="Not invoked.")

        base: dict = {"status": result.status.value, "summary": result.summary}
        if result.agent_name == SubagentName.CUSTOMER_INSIGHTS:
            base["key_evidence"] = result.data.get("evidence", [])
            base["customer_segments"] = result.data.get("customer_segments", [])
            base["demand_strength"] = result.data.get("demand_strength", "unknown")
        elif result.agent_name == SubagentName.MARKET_RESEARCH:
            base["key_evidence"] = result.data.get("competitor_findings", [])
            base["market_expectation"] = result.data.get("market_expectation", "unknown")
            base["differentiation_opportunities"] = result.data.get("differentiation_opportunities", [])
        elif result.agent_name == SubagentName.TECHNICAL_FEASIBILITY:
            base["effort"] = result.data.get("effort", "Unknown")
            base["dependencies"] = result.data.get("dependencies", [])
            base["affected_systems"] = result.data.get("affected_systems", [])
        elif result.agent_name == SubagentName.RISK_AND_METRICS:
            base["risks"] = result.data.get("risks", [])
            base["success_metrics"] = result.data.get("success_metrics", [])

        if result.limitations:
            base["limitations"] = result.limitations
        return SubagentBriefSection(**base)
