"""流式事件契约（schemaVersion 3）。

Web SSE 与 CLI --format streaming-json 共用同一 payload 形状。
传输层差异：Web 包成 SSE event:message（带 id: eventId）；CLI 打成 NDJSON 行。

v2 新增公共字段：runId、eventId；可选 checkpointId。
"""
from __future__ import annotations

from typing import Any, Literal, TypedDict

SCHEMA_VERSION = 3

# v2 冻结集合（生产路径会发出）
EventType = Literal[
    "start",
    "delta",
    "thinking",
    "thinking_delta",
    "tool_call",
    "tool_result",
    "subagent_start",
    "subagent_done",
    "interrupt",
    "artifact",
    "done",
    "error",
]

# deferred：文档保留、实现暂不发或形态不同
# - tool（旧协议）
# - usage（前端已有 handler，后端可后续接入）
# - ping（库级 SSE comment keep-alive，非 JSON 事件）

V1_EVENT_TYPES: frozenset[str] = frozenset({
    "start",
    "delta",
    "thinking",
    "thinking_delta",
    "tool_call",
    "tool_result",
    "subagent_start",
    "subagent_done",
    "interrupt",
    "artifact",
    "done",
    "error",
})

# 别名：v2 事件类型集合与 v1 相同，仅公共字段扩展
V2_EVENT_TYPES = V1_EVENT_TYPES
V3_EVENT_TYPES = V1_EVENT_TYPES


class StreamEvent(TypedDict, total=False):
    type: str
    schemaVersion: int
    messageId: str
    runId: str
    eventId: str
    checkpointId: str
    delta: str
    callId: str
    name: str
    args: Any
    output: str
    subagentId: str
    subagentType: str
    description: str
    groups: list
    message: str
    path: str
    url: str
    mime: str
    size: int
    denied: bool


def make_event_id(run_id: str, seq: int) -> str:
    """构造单调 eventId：`{runId}:{seq}`。"""
    return f"{run_id}:{seq}"


def make_event(
    event_type: str,
    *,
    include_version: bool | None = None,
    run_id: str | None = None,
    event_id: str | None = None,
    seq: int | None = None,
    **fields: Any,
) -> dict[str, Any]:
    """构造一条流式事件 dict。

    start / done 默认带 schemaVersion；其余事件默认不带（减小带宽），
    调用方可传 include_version=True 强制带上（CLI NDJSON 单行自描述时有用）。

    若提供 run_id：自动注入 runId；若同时给 seq 或 event_id，注入 eventId。
    """
    if include_version is None:
        include_version = event_type in ("start", "done")
    payload: dict[str, Any] = {"type": event_type, **fields}
    if include_version:
        payload["schemaVersion"] = SCHEMA_VERSION
    if run_id:
        payload["runId"] = run_id
        if event_id:
            payload["eventId"] = event_id
        elif seq is not None:
            payload["eventId"] = make_event_id(run_id, seq)
    return payload
