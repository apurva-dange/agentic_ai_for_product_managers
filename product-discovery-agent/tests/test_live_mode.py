"""Tests for the live (real API) mode's pure/offline-testable pieces.

These tests never make a real network call - they exercise JSON parsing,
schema shape, error handling, and dispatch wiring only, so the test suite
stays free, fast, and deterministic even though live mode itself is not.
"""

from __future__ import annotations

import pytest

import live_tools
from llm.openrouter_client import OpenRouterClient, OpenRouterError, get_api_key


def test_get_api_key_raises_clearly_when_missing(monkeypatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr("llm.openrouter_client._load_dotenv_if_present", lambda: None)

    with pytest.raises(OpenRouterError):
        get_api_key()


def test_get_api_key_reads_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-key")
    monkeypatch.setattr("llm.openrouter_client._load_dotenv_if_present", lambda: None)

    assert get_api_key() == "sk-or-test-key"


def test_extract_json_parses_plain_json() -> None:
    result = OpenRouterClient.extract_json('{"a": 1, "b": [2, 3]}')
    assert result == {"a": 1, "b": [2, 3]}


def test_extract_json_parses_fenced_json() -> None:
    text = '```json\n{"recommendation": "Build now"}\n```'
    result = OpenRouterClient.extract_json(text)
    assert result == {"recommendation": "Build now"}


def test_extract_json_parses_json_with_surrounding_prose() -> None:
    text = 'Sure, here is my answer:\n{"confidence": "High"}\nLet me know if you need more.'
    result = OpenRouterClient.extract_json(text)
    assert result == {"confidence": "High"}


def test_extract_json_raises_on_no_json_object() -> None:
    with pytest.raises(OpenRouterError):
        OpenRouterClient.extract_json("no json here at all")


def test_tool_schemas_match_openai_function_calling_shape() -> None:
    for schema in live_tools.TOOL_SCHEMAS:
        assert schema["type"] == "function"
        func = schema["function"]
        assert func["name"]
        assert func["description"]
        assert func["parameters"]["type"] == "object"
        assert "feature_name" in func["parameters"]["properties"]
        assert "feature_name" in func["parameters"]["required"]


def test_tool_schema_names_match_dispatch_table() -> None:
    schema_names = {schema["function"]["name"] for schema in live_tools.TOOL_SCHEMAS}
    dispatch_names = set(live_tools._DISPATCH.keys())
    assert schema_names == dispatch_names


def test_execute_live_tool_dispatches_by_name(monkeypatch) -> None:
    calls = []

    def fake_tool(feature_name: str, client=None, **kwargs):
        calls.append((feature_name, kwargs))
        return {"ok": True}

    monkeypatch.setitem(live_tools._DISPATCH, "customer_feedback_search", fake_tool)

    result = live_tools.execute_live_tool(
        "customer_feedback_search", {"feature_name": "dark mode"}, client=object()
    )

    assert result == {"ok": True}
    assert calls == [("dark mode", {})]


def test_execute_live_tool_raises_on_unknown_tool_name() -> None:
    with pytest.raises(KeyError):
        live_tools.execute_live_tool("not_a_real_tool", {"feature_name": "x"}, client=object())
