"""Tests for the structured message history (requirement: tool results must
always be appended to history) and trace export (requirement 20)."""

from __future__ import annotations

import json

from history import MessageHistory
from models import MessageRole, ToolName, ToolResult, ToolStatus


def make_success_result() -> ToolResult:
    return ToolResult(
        tool_call_id="call_001",
        tool_name=ToolName.CUSTOMER_FEEDBACK_SEARCH,
        status=ToolStatus.SUCCESS,
        data={"total_matching_requests": 42},
    )


def test_sequence_numbers_increase_monotonically() -> None:
    history = MessageHistory()
    history.add_user_message("Should we build dark mode?")
    history.add_assistant_analysis("Deciding what evidence is needed.")
    entries = history.entries
    assert entries[0].sequence < entries[1].sequence


def test_add_tool_result_appends_with_correct_metadata() -> None:
    history = MessageHistory()
    result = make_success_result()
    history.add_tool_result(result, "SUCCESS: returned fields [...]")

    tool_result_entries = [e for e in history.entries if e.role == MessageRole.TOOL_RESULT]
    assert len(tool_result_entries) == 1
    entry = tool_result_entries[0]
    assert entry.tool_name == ToolName.CUSTOMER_FEEDBACK_SEARCH
    assert entry.tool_call_id == "call_001"
    assert entry.status == ToolStatus.SUCCESS


def test_render_trace_includes_all_roles() -> None:
    history = MessageHistory()
    history.add_user_message("Should we build dark mode?")
    history.add_assistant_analysis("Planning evidence needs.")
    history.add_assistant_tool_use(ToolName.CUSTOMER_FEEDBACK_SEARCH, "call_001", "Calling tool")
    history.add_tool_result(make_success_result(), "SUCCESS")
    history.add_assistant_final("Recommendation ready.")

    trace = history.render_trace()
    assert "USER" in trace
    assert "ASSISTANT_ANALYSIS" in trace
    assert "ASSISTANT_TOOL_USE" in trace
    assert "TOOL_RESULT" in trace
    assert "ASSISTANT_FINAL" in trace


def test_save_trace_round_trips_to_json(tmp_path) -> None:
    history = MessageHistory()
    history.add_user_message("Should we build dark mode?")
    history.add_tool_result(make_success_result(), "SUCCESS")

    output_path = tmp_path / "trace.json"
    saved_path = history.save_trace(output_path)

    assert saved_path.exists()
    loaded = json.loads(saved_path.read_text())
    assert len(loaded) == len(history.entries)
    assert loaded[0]["role"] == "user"
    assert loaded[1]["role"] == "tool_result"
    assert loaded[1]["tool_name"] == "customer_feedback_search"
