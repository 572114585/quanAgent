"""CLI NDJSON observability contracts."""
from __future__ import annotations

from langchain_core.messages import AIMessageChunk, ToolMessage

import entrypoints.cli as cli


def test_tool_start_is_emitted_before_tool_result(monkeypatch):
    events = []
    monkeypatch.setattr(cli, "emit_ndjson", events.append)
    cli._pending_tool_calls.clear()
    chunk = AIMessageChunk(
        content="",
        tool_call_chunks=[{
            "name": "research_search", "args": '{"query":"secret',
            "id": "tc-1", "index": 0, "type": "tool_call_chunk",
        }],
    )
    cli.log_tool_call(chunk, json_mode=True)
    assert [event["type"] for event in events] == ["tool_call"]
    assert events[0]["args"] == ""
    cli.log_tool_call(
        ToolMessage(content='{"ok":true}', tool_call_id="tc-1", name="research_search"),
        json_mode=True,
    )
    assert [event["type"] for event in events] == ["tool_call", "tool_result"]
