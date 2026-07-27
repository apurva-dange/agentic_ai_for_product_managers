"""Shared subagent interface, error types, and tool-scoping enforcement.

Every specialist subagent is a small class that implements `run(task,
context) -> AgentResult`. The base class supplies the one thing that must be
consistent across all of them: a `call_tool` method that only allows the
tools that agent's role was explicitly granted (`allowed_tools`), so a
misconfigured or overreaching agent fails loudly with a structured error
instead of silently reaching into another agent's data source.
"""

from __future__ import annotations

from typing import Any, ClassVar, Optional, Protocol

from coordinator.models import AgentResult, AgentTask, ContextPackage, SubagentName
from models import ToolName
from tools import execute_tool


class SubagentError(Exception):
    """Base class for structured, expected subagent failure modes."""


class MissingContextError(SubagentError):
    """Raised when a subagent's ContextPackage is missing a required field.

    Carries the field name so the coordinator can decide whether it has a
    safe fallback value it can supply on a retry (see retry_policy.py).
    """

    def __init__(self, field_name: str, message: Optional[str] = None) -> None:
        self.field_name = field_name
        super().__init__(message or f"Missing required context field: '{field_name}'.")


class ToolNotAuthorizedError(SubagentError):
    """Raised when a subagent attempts to call a tool outside its role."""

    def __init__(self, agent_name: SubagentName, tool_name: ToolName) -> None:
        self.agent_name = agent_name
        self.tool_name = tool_name
        super().__init__(
            f"{agent_name.value} is not authorized to call '{tool_name.value}'."
        )


class UnknownAgentError(SubagentError):
    """Raised when the coordinator is asked to invoke an unregistered agent."""

    def __init__(self, agent_name: str) -> None:
        self.agent_name = agent_name
        super().__init__(f"No subagent is registered under the name '{agent_name}'.")


class Subagent(Protocol):
    """Structural interface every specialist subagent satisfies."""

    name: SubagentName

    def run(self, task: AgentTask, context: ContextPackage) -> AgentResult: ...


class BaseSubagent:
    """Common scaffolding for specialist subagents: identity + tool scoping."""

    name: ClassVar[SubagentName]
    allowed_tools: ClassVar[frozenset[ToolName]] = frozenset()

    def __init__(self, force_failure: bool = False) -> None:
        # Test/demo hook only: simulates an unhandled subagent execution
        # failure (spec scenario 15.1), never triggered by real evidence.
        self.force_failure = force_failure

    def call_tool(self, tool_name: ToolName, **tool_input: Any) -> dict[str, Any]:
        if tool_name not in self.allowed_tools:
            raise ToolNotAuthorizedError(self.name, tool_name)
        return execute_tool(tool_name, tool_input)

    def run(self, task: AgentTask, context: ContextPackage) -> AgentResult:
        raise NotImplementedError
