"""Shared error type for tool execution failures.

Tools raise ToolExecutionError for expected, recoverable failure modes
(unknown feature, simulated transient outage). The agent loop catches this
specifically rather than swallowing every exception, so genuine bugs in tool
code still surface as real stack traces.
"""

from __future__ import annotations


class ToolExecutionError(Exception):
    """Raised by a tool when it cannot produce a result for a valid request."""
