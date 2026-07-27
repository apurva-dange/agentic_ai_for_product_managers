"""A deliberately simple, explainable retry policy.

Only a missing-context failure is retried, and only when the coordinator has
a safe fallback value to supply for the missing field. Execution failures,
authorization failures, and unknown-agent errors are never retried - retrying
those would either repeat the same crash or paper over a real
misconfiguration.
"""

from __future__ import annotations

from dataclasses import dataclass

from subagents.base import MissingContextError, SubagentError, ToolNotAuthorizedError, UnknownAgentError

MAX_RETRIES = 1


@dataclass
class RetryDecision:
    should_retry: bool
    reason: str


class RetryPolicy:
    """Decides whether a failed subagent invocation should be retried."""

    max_retries: int = MAX_RETRIES

    def evaluate(self, error: Exception, attempt_number: int, has_fallback: bool) -> RetryDecision:
        if attempt_number > self.max_retries:
            return RetryDecision(False, "retry limit reached")

        if isinstance(error, MissingContextError):
            if has_fallback:
                return RetryDecision(True, f"missing context '{error.field_name}' can be safely supplied")
            return RetryDecision(False, f"missing context '{error.field_name}' has no safe fallback available")

        if isinstance(error, ToolNotAuthorizedError):
            return RetryDecision(False, "authorization failures are not retried")

        if isinstance(error, UnknownAgentError):
            return RetryDecision(False, "unknown-agent errors are not retried without reconfiguration")

        if isinstance(error, SubagentError):
            return RetryDecision(False, "business-rule failure; not retried")

        # Any other exception is treated as a hard execution failure for this
        # teaching demo. A future iteration could distinguish transient
        # infrastructure errors here and retry them.
        return RetryDecision(False, "execution failure; not retried")
