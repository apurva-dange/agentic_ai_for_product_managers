"""Builds the final structured Recommendation from collected evidence.

The scoring here is a deliberately simple, deterministic, and explainable
rule set (demand, usage signal, competitor pressure, effort, risk) - a
teaching example of how evidence maps to a recommendation, not a real
prioritization algorithm.
"""

from __future__ import annotations

from typing import Optional

from models import EvidencePlan, EvidenceType, Recommendation

EFFORT_PENALTY = {"Low": 0, "Medium": -1, "High": -2, "Unknown": -1}

SUCCESS_METRICS: dict[str, list[str]] = {
    "dark_mode": [
        "Percentage of active users who enable dark mode within 30 days (proposed)",
        "Change in evening-session duration after release (proposed)",
        "Change in evening-session abandonment rate after release (proposed)",
        "Volume of accessibility-related support tickets after release (proposed)",
        "Dark mode retention rate after 30 days (proposed)",
    ],
    "mobile_app": [
        "Percentage of eligible users who install the mobile app within 60 days (proposed)",
        "Mobile task completion rate vs. desktop (proposed)",
        "Change in mobile web task abandonment after launch (proposed)",
        "App store rating and crash-free session rate (proposed)",
        "30-day mobile app retention rate (proposed)",
    ],
    "ai_meeting_summary": [
        "Percentage of recorded calls with an AI summary reviewed by a user (proposed)",
        "Change in calls with a completed follow-up task within 48 hours (proposed)",
        "User-reported summary accuracy/edit rate (proposed)",
        "Time saved on manual note-taking, self-reported (proposed)",
        "Opt-in rate for call summarization (proposed)",
    ],
    "onboarding": [
        "Percentage of new accounts completing setup within 7 days (proposed)",
        "Median time-to-first-value for new accounts (proposed)",
        "Support tickets per new account in the first week (proposed)",
        "7-day and 30-day retention for new accounts (proposed)",
    ],
    "export_pdf": [
        "Number of PDF exports per month (proposed)",
        "Percentage of report views that result in a PDF export (proposed)",
        "Reduction in manual/workaround export support tickets (proposed)",
    ],
}

DEFAULT_SUCCESS_METRICS = [
    "Feature adoption rate within 30 days of release (proposed)",
    "Related support ticket volume before vs. after release (proposed)",
    "User retention among adopters after 30 days (proposed)",
]


def _demand_score(feedback: Optional[dict]) -> int:
    if not feedback:
        return 0
    total = feedback.get("total_matching_requests", 0)
    if total >= 30:
        return 2
    if total >= 15:
        return 1
    return 0


def _analytics_signal(analytics: Optional[dict]) -> int:
    if not analytics:
        return 0
    rates = analytics.get("drop_off_rates", {})
    numeric_rates = [v for v in rates.values() if isinstance(v, (int, float))]
    return 1 if any(rate > 25 for rate in numeric_rates) else 0


def _competitor_pressure(competitor: Optional[dict]) -> int:
    if not competitor:
        return 0
    return 1 if competitor.get("competitors_offering") else 0


def _executive_summary(
    feature_display_name: str,
    recommendation_value: str,
    collected: set[EvidenceType],
    demand_score: int,
    effort_level: str,
    risk_levels: list[str],
) -> str:
    if recommendation_value == "Insufficient evidence":
        return (
            f"No usable evidence could be gathered for '{feature_display_name}'. "
            "A human product manager should investigate manually before any decision is made."
        )

    parts = []
    if EvidenceType.CUSTOMER_FEEDBACK in collected:
        demand_phrase = {0: "limited", 1: "moderate", 2: "meaningful"}[demand_score]
        parts.append(f"there is {demand_phrase} customer demand")
    if EvidenceType.PRODUCT_ANALYTICS in collected:
        parts.append("usage analytics offer a related (correlational, not causal) signal")
    if EvidenceType.ENGINEERING_EFFORT in collected:
        parts.append(f"estimated engineering effort is {effort_level.lower()}")
    if EvidenceType.RISKS in collected and risk_levels:
        parts.append(f"identified risk levels include {', '.join(sorted(set(risk_levels)))}")

    evidence_phrase = "; ".join(parts) if parts else "only partial evidence was available"
    return (
        f"For '{feature_display_name}': {evidence_phrase}. "
        f"Based on this evidence, the suggested next step is: {recommendation_value.lower()}."
    )


def build_recommendation(
    feature_display_name: str,
    evidence_plan: EvidencePlan,
    evidence_data: dict[EvidenceType, dict],
    stop_reason: str,
    feature_key: Optional[str] = None,
) -> Recommendation:
    """Turn collected evidence into a structured, schema-validated Recommendation."""

    collected = set(evidence_plan.collected)
    failed = set(evidence_plan.permanently_failed)

    feedback = evidence_data.get(EvidenceType.CUSTOMER_FEEDBACK)
    analytics = evidence_data.get(EvidenceType.PRODUCT_ANALYTICS)
    competitor = evidence_data.get(EvidenceType.COMPETITOR_RESEARCH)
    effort = evidence_data.get(EvidenceType.ENGINEERING_EFFORT)
    risk = evidence_data.get(EvidenceType.RISKS)

    limitations: list[str] = []
    assumptions: list[str] = []
    next_steps: list[str] = []

    if stop_reason != "end_turn":
        limitations.append(
            f"This run halted early (stop_reason='{stop_reason}') before the evidence "
            "plan fully completed; treat this recommendation as provisional."
        )

    if not collected:
        return Recommendation(
            feature=feature_display_name,
            recommendation="Insufficient evidence",
            confidence="Low",
            executive_summary=_executive_summary(
                feature_display_name, "Insufficient evidence", collected, 0, "Unknown", []
            ),
            evidence={
                "customer_feedback": [],
                "product_analytics": [],
                "competitor_research": [],
                "engineering_effort": [],
                "risks": [],
            },
            assumptions=[],
            limitations=limitations
            + ["No synthetic evidence could be matched or retrieved for this feature."],
            recommended_next_steps=[
                "Conduct manual discovery: interview customers, review support "
                "tickets, and scope a lightweight technical spike before deciding.",
            ],
            success_metrics=[],
            human_decision_required=True,
        )

    demand_score = _demand_score(feedback)
    analytics_signal = _analytics_signal(analytics)
    competitor_pressure = _competitor_pressure(competitor)
    effort_level = effort["estimated_effort_level"] if effort else "Unknown"
    effort_penalty = EFFORT_PENALTY[effort_level]

    risk_levels = [r["level"] for r in risk["risks"]] if risk else []
    risk_penalty = 0
    if "High" in risk_levels:
        risk_penalty = -2
    elif "Medium" in risk_levels:
        risk_penalty = -1

    if feedback:
        assumptions.append(
            f"Assumes the {feedback['total_matching_requests']} synthetic customer "
            "requests are representative of broader demand."
        )
    else:
        limitations.append("Customer demand evidence was not available.")

    if analytics:
        limitations.extend(analytics.get("data_limitations", [])[:2])
    else:
        limitations.append("Product usage analytics were not available.")

    if effort:
        limitations.append(
            "Engineering effort is a relative, teaching-purpose estimate, not a "
            "committed production estimate."
        )
    else:
        limitations.append("Engineering effort evidence was not available.")

    if risk:
        for r in risk["risks"]:
            next_steps.append(f"Review: {r['recommended_review']} ({r['category']}, {r['level']} risk).")
    else:
        limitations.append("Risk and compliance evidence was not available.")

    score = demand_score + analytics_signal + competitor_pressure + effort_penalty + risk_penalty
    critical_missing = (
        EvidenceType.CUSTOMER_FEEDBACK not in collected
        or EvidenceType.ENGINEERING_EFFORT not in collected
    )

    if critical_missing:
        recommendation_value = "Investigate further"
    elif score >= 3:
        recommendation_value = "Build now"
    elif score >= 1:
        recommendation_value = "Add to roadmap"
    elif score == 0:
        recommendation_value = "Run an experiment"
    elif score >= -2:
        recommendation_value = "Investigate further"
    else:
        recommendation_value = "Do not prioritize"

    n_collected = len(collected)
    if evidence_plan.is_complete() and stop_reason == "end_turn":
        confidence = "High" if not failed else "Medium"
    elif n_collected >= 3:
        confidence = "Medium"
    else:
        confidence = "Low"

    if failed:
        limitations.append(
            f"Could not obtain evidence for: {', '.join(e.value for e in failed)} "
            "after retries; this recommendation reflects partial evidence."
        )

    if not next_steps:
        next_steps.append(
            "Validate findings with direct customer interviews before committing engineering resources."
        )
    if failed:
        next_steps.append("Re-run this analysis once the missing evidence sources are available.")

    metrics = SUCCESS_METRICS.get(feature_key or "", DEFAULT_SUCCESS_METRICS)

    evidence_payload = {
        "customer_feedback": [feedback] if feedback else [],
        "product_analytics": [analytics] if analytics else [],
        "competitor_research": [competitor] if competitor else [],
        "engineering_effort": [effort] if effort else [],
        "risks": risk["risks"] if risk else [],
    }

    return Recommendation(
        feature=feature_display_name,
        recommendation=recommendation_value,
        confidence=confidence,
        executive_summary=_executive_summary(
            feature_display_name, recommendation_value, collected, demand_score, effort_level, risk_levels
        ),
        evidence=evidence_payload,
        assumptions=assumptions,
        limitations=limitations,
        recommended_next_steps=next_steps,
        success_metrics=metrics,
        human_decision_required=True,
    )
