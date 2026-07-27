"""The core agentic loop.

This is a direct implementation of the required control flow:

    while iteration < max_iterations:
        response = model.respond(message_history)
        if response.stop_reason == "tool_use":
            append_assistant_response_to_history(response)
            execute_requested_tools(response)
            append_tool_results_to_history()
            continue
        if response.stop_reason == "end_turn":
            return final_response
        handle_unknown_stop_reason()

Tool execution and evidence bookkeeping are delegated to the `on_tool_use`
callback (owned by the agent) because they depend on evidence-plan and
bug-mode state that this generic loop doesn't need to know about. Everything
else - reading the model's stop reason, updating history for non-tool
messages, and enforcing the iteration cap - lives here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from history import MessageHistory
from logging_utils import EventLogger
from models import EvidencePlan, ModelResponse, StopReason


class RespondingModel(Protocol):
    def respond(self, evidence_plan: EvidencePlan, iteration: int) -> ModelResponse: ...


@dataclass
class LoopOutcome:
    """Describes how and why the loop terminated."""

    stop_reason: str
    iterations_used: int


def run_loop(
    model: RespondingModel,
    history: MessageHistory,
    evidence_plan: EvidencePlan,
    on_tool_use: Callable[[ModelResponse, int], bool],
    logger: EventLogger,
    max_iterations: int,
) -> LoopOutcome:
    """Run the agentic loop until it reaches a stopping condition.

    Args:
        model: Anything with a `respond(evidence_plan, iteration)` method.
        history: The structured message history to append to.
        evidence_plan: Tracks required/collected/permanently-failed evidence.
        on_tool_use: Callback invoked for a `tool_use` response. Must execute
            the requested tool(s), append tool results to history (unless a
            bug mode intentionally skips that), and update evidence_plan.
            Returns True if the loop should stop immediately afterward
            (used by the `end-too-early` bug mode demonstration).
        logger: Console event logger.
        max_iterations: Hard cap on loop iterations (max iteration protection).

    Returns:
        A LoopOutcome describing why the loop stopped.
    """

    iteration = 0
    while iteration < max_iterations:
        iteration += 1
        response = model.respond(evidence_plan, iteration)
        logger.log_iteration_header(iteration, max_iterations, evidence_plan)

        if response.stop_reason == StopReason.TOOL_USE:
            history.add_assistant_analysis(response.analysis_summary)
            logger.log_reasoning(response.analysis_summary)

            stop_early = on_tool_use(response, iteration)
            if stop_early:
                return LoopOutcome(stop_reason="bug_mode_end_too_early", iterations_used=iteration)
            continue

        if response.stop_reason == StopReason.END_TURN:
            history.add_assistant_final(response.final_text)
            logger.log_final(response)
            return LoopOutcome(stop_reason="end_turn", iterations_used=iteration)

        # Unknown or unsupported stop reason: handle safely instead of
        # crashing or looping forever on an unrecognized signal.
        history.add_assistant_final(
            f"Run halted: model returned an unsupported stop_reason '{response.stop_reason.value}'."
        )
        logger.log_unknown_stop_reason(response)
        return LoopOutcome(stop_reason="unknown_stop_reason", iterations_used=iteration)

    logger.log_max_iterations_reached(max_iterations)
    return LoopOutcome(stop_reason="max_iterations_reached", iterations_used=max_iterations)
