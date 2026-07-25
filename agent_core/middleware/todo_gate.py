"""End-of-turn Todo Gate（对齐 grok-build）。

模型若在仍有 pending/in_progress todos 时发出「纯文本、无 tool call」结束回合，
本 middleware 注入 system-reminder 并 jump_to=model 强制续跑。
"""
from __future__ import annotations

from typing import Annotated, Any, NotRequired

from langchain.agents.middleware.types import (
    AgentMiddleware,
    AgentState,
    PrivateStateAttr,
    hook_config,
)
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.runtime import Runtime
from typing_extensions import override


def _todo_status(todo: Any) -> str:
    if isinstance(todo, dict):
        return str(todo.get("status") or "")
    return str(getattr(todo, "status", "") or "")


def _todo_content(todo: Any) -> str:
    if isinstance(todo, dict):
        return str(todo.get("content") or "")
    return str(getattr(todo, "content", "") or "")


def open_todos(todos: list[Any] | None) -> list[Any]:
    """返回尚未完成的 todos（pending / in_progress）。"""
    out: list[Any] = []
    for t in todos or []:
        if _todo_status(t) in ("pending", "in_progress"):
            out.append(t)
    return out


def format_open_todos(todos: list[Any]) -> str:
    lines: list[str] = []
    for t in todos:
        lines.append(f"- [{_todo_status(t)}] {_todo_content(t)}")
    return "\n".join(lines) if lines else "(none)"


def build_todo_gate_reminder(todos: list[Any]) -> str:
    return (
        "<system-reminder>\n"
        "## End-of-turn Todo Gate\n"
        "You attempted to end the turn while todos remain unfinished:\n"
        f"{format_open_todos(todos)}\n\n"
        "You may NOT end with a content-only message. Either:\n"
        "1. Advance the next pending/in_progress todo with a tool call in this response, OR\n"
        "2. Remove blocked items via write_todos and state the hard blocker explicitly "
        "(missing credentials / denied permission / external outage).\n\n"
        "Do not ask the user whether to continue. Do not write a summary and stop.\n"
        "</system-reminder>"
    )


class TodoGateState(AgentState):
    """Todo gate 私有计数：连续 nudge 次数，避免死循环。"""

    _todo_gate_nudges: NotRequired[Annotated[int, PrivateStateAttr]]


class TodoGateMiddleware(AgentMiddleware[TodoGateState]):
    """有未完成 todos 时禁止以无 tool call 的 AIMessage 结束回合。"""

    state_schema = TodoGateState  # type: ignore[assignment]

    def __init__(self, *, max_nudges: int = 3) -> None:
        super().__init__()
        self.max_nudges = max(1, int(max_nudges))

    @hook_config(can_jump_to=["model"])
    @override
    def after_model(self, state: TodoGateState, runtime: Runtime) -> dict[str, Any] | None:  # noqa: ARG002
        messages = state.get("messages") or []
        if not messages:
            return None

        last = messages[-1]
        if not isinstance(last, AIMessage):
            return None

        tool_calls = getattr(last, "tool_calls", None) or []
        if tool_calls:
            # 有工具调用 → 在推进中，重置 nudge 计数
            if state.get("_todo_gate_nudges"):
                return {"_todo_gate_nudges": 0}
            return None

        unfinished = open_todos(state.get("todos"))  # type: ignore[arg-type]
        if not unfinished:
            if state.get("_todo_gate_nudges"):
                return {"_todo_gate_nudges": 0}
            return None

        nudges = int(state.get("_todo_gate_nudges") or 0)
        if nudges >= self.max_nudges:
            # 连续 nudge 无效：放行结束，避免无限循环
            return {"_todo_gate_nudges": 0}

        reminder = HumanMessage(content=build_todo_gate_reminder(unfinished))
        return {
            "messages": [reminder],
            "jump_to": "model",
            "_todo_gate_nudges": nudges + 1,
        }

    @override
    async def aafter_model(
        self, state: TodoGateState, runtime: Runtime
    ) -> dict[str, Any] | None:
        return self.after_model(state, runtime)
