"""Tests for RetryPolicy (Module 2 requirements 14, 15, and spec section 16)."""

from __future__ import annotations

from coordinator.models import SubagentName
from coordinator.retry_policy import RetryPolicy
from subagents.base import MissingContextError, ToolNotAuthorizedError, UnknownAgentError
from models import ToolName

POLICY = RetryPolicy()


def test_missing_context_with_fallback_is_retried() -> None:
    error = MissingContextError("platforms")
    decision = POLICY.evaluate(error, attempt_number=1, has_fallback=True)
    assert decision.should_retry is True


def test_missing_context_without_fallback_is_not_retried() -> None:
    error = MissingContextError("some_unsuppliable_field")
    decision = POLICY.evaluate(error, attempt_number=1, has_fallback=False)
    assert decision.should_retry is False


def test_retry_limit_is_respected() -> None:
    error = MissingContextError("platforms")
    decision = POLICY.evaluate(error, attempt_number=2, has_fallback=True)
    assert decision.should_retry is False
    assert "limit" in decision.reason


def test_authorization_failure_is_never_retried() -> None:
    error = ToolNotAuthorizedError(SubagentName.CUSTOMER_INSIGHTS, ToolName.ENGINEERING_EFFORT_ESTIMATOR)
    decision = POLICY.evaluate(error, attempt_number=1, has_fallback=True)
    assert decision.should_retry is False


def test_unknown_agent_error_is_never_retried() -> None:
    error = UnknownAgentError("not_a_real_agent")
    decision = POLICY.evaluate(error, attempt_number=1, has_fallback=True)
    assert decision.should_retry is False


def test_generic_execution_failure_is_not_retried() -> None:
    decision = POLICY.evaluate(RuntimeError("boom"), attempt_number=1, has_fallback=False)
    assert decision.should_retry is False
