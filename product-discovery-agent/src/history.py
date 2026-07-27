"""Structured conversation/message history for the agentic loop.

The agent's ability to reason across multiple tool calls depends entirely on
every tool call and every tool result being appended to this history and fed
back to the (simulated) model on the next iteration. This module is the
single place that owns that history so the loop, the mock model, and the CLI
all see a consistent, ordered trace of the run.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from models import (
    HistoryEntry,
    MessageRole,
    ToolName,
    ToolResult,
    ToolStatus,
    next_sequence_number,
)


class MessageHistory:
    """An append-only, ordered log of everything that happened during a run."""

    def __init__(self) -> None:
        self._entries: list[HistoryEntry] = []

    def __len__(self) -> int:
        return len(self._entries)

    @property
    def entries(self) -> list[HistoryEntry]:
        return list(self._entries)

    def _append(
        self,
        role: MessageRole,
        content: str,
        tool_name: Optional[ToolName] = None,
        tool_call_id: Optional[str] = None,
        status: Optional[ToolStatus] = None,
    ) -> HistoryEntry:
        entry = HistoryEntry(
            sequence=next_sequence_number(),
            role=role,
            content=content,
            timestamp=HistoryEntry.now_iso(),
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            status=status,
        )
        self._entries.append(entry)
        return entry

    def add_user_message(self, content: str) -> HistoryEntry:
        return self._append(MessageRole.USER, content)

    def add_assistant_analysis(self, content: str) -> HistoryEntry:
        return self._append(MessageRole.ASSISTANT_ANALYSIS, content)

    def add_assistant_tool_use(
        self, tool_name: ToolName, tool_call_id: str, tool_input_summary: str
    ) -> HistoryEntry:
        return self._append(
            MessageRole.ASSISTANT_TOOL_USE,
            tool_input_summary,
            tool_name=tool_name,
            tool_call_id=tool_call_id,
        )

    def add_tool_result(self, result: ToolResult, summary: str) -> HistoryEntry:
        """Append a tool result to history.

        This is the step that must never be skipped: without it, the next
        model turn has no way to know a tool already ran, which is exactly
        what the `skip-tool-history` bug mode demonstrates.
        """

        return self._append(
            MessageRole.TOOL_RESULT,
            summary,
            tool_name=result.tool_name,
            tool_call_id=result.tool_call_id,
            status=result.status,
        )

    def add_assistant_final(self, content: str) -> HistoryEntry:
        return self._append(MessageRole.ASSISTANT_FINAL, content)

    def render_trace(self) -> str:
        """Render a human-readable trace of the full run, in order."""

        lines: list[str] = ["=" * 72, "CONVERSATION HISTORY TRACE", "=" * 72]
        for entry in self._entries:
            header = f"[{entry.sequence:03d}] {entry.role.value.upper()}"
            if entry.tool_name:
                header += f" ({entry.tool_name.value})"
            if entry.status:
                header += f" - {entry.status.value}"
            lines.append(header)
            lines.append(f"    {entry.content}")
        lines.append("=" * 72)
        return "\n".join(lines)

    def to_json_dict(self) -> list[dict]:
        return [json.loads(entry.model_dump_json()) for entry in self._entries]

    def save_trace(self, path: str | Path) -> Path:
        """Persist the full trace as JSON for later inspection or portfolio use."""

        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(self.to_json_dict(), indent=2))
        return output_path
