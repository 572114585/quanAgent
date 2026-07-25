"""上下文压缩后强制重种 todos（对齐 grok-build Pre-Compaction Todo List）。"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Annotated, Any, NotRequired

from langchain.agents.middleware.types import (
    AgentMiddleware,
    AgentState,
    ExtendedModelResponse,
    ModelRequest,
    ModelResponse,
    PrivateStateAttr,
)
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.runtime import Runtime
from langgraph.types import Command
from typing_extensions import override

from agent_core.middleware.todo_gate import format_open_todos, open_todos


def is_summary_message(msg: Any) -> bool:
    if not isinstance(msg, HumanMessage):
        return False
    kwargs = getattr(msg, "additional_kwargs", None) or {}
    return kwargs.get("lc_source") == "summarization"


def has_pre_compaction_reminder(messages: list[Any]) -> bool:
    for m in messages:
        if not isinstance(m, HumanMessage):
            continue
        content = getattr(m, "content", "") or ""
        if isinstance(content, list):
            content = str(content)
        if "Pre-Compaction Todo List" in str(content):
            return True
    return False


def build_pre_compaction_reminder(todos: list[Any]) -> str:
    return (
        "<system-reminder>\n"
        "## Pre-Compaction Todo List\n"
        "Context was compacted. Your prior todo list may no longer appear in conversation "
        "history. Your FIRST tool call MUST be write_todos (full replace) reconstructing "
        "the remaining work from this snapshot before any other action:\n"
        f"{format_open_todos(todos)}\n\n"
        "Do not advance other steps until the list is restored.\n"
        "</system-reminder>"
    )


def _event_key(event: Any) -> str | None:
    if not isinstance(event, dict):
        return None
    cutoff = event.get("cutoff_index")
    if cutoff is None:
        return None
    summary = event.get("summary_message")
    summary_snip = ""
    if summary is not None:
        content = getattr(summary, "content", "") or ""
        if isinstance(content, list):
            content = str(content)[:80]
        summary_snip = str(content)[:80]
    return f"{cutoff}:{summary_snip}"


class CompactReseedState(AgentState):
    _needs_todo_reseed: NotRequired[Annotated[bool, PrivateStateAttr]]
    _compact_reseed_event_key: NotRequired[Annotated[str | None, PrivateStateAttr]]
    # SummarizationMiddleware 写入；声明以便类型合并时可见
    _summarization_event: NotRequired[Annotated[Any, PrivateStateAttr]]


class CompactReseedMiddleware(AgentMiddleware[CompactReseedState]):
    """压缩后注入 Pre-Compaction Todo List，并拦截非 write_todos 的工具调用。

    SummarizationMiddleware 在用户 middleware 之外层；其 wrap_model_call 会先压缩
    messages 再调用内层 handler。因此本类在 wrap_model_call 中能直接看到带
    lc_source=summarization 的摘要消息，并在同一次 model 调用前注入 reminder。
    """

    state_schema = CompactReseedState  # type: ignore[assignment]

    def _maybe_inject(
        self, request: ModelRequest
    ) -> tuple[ModelRequest, bool]:
        """若 messages 含摘要且有未完成 todos，注入 reminder。返回 (request, needs_reseed)。"""
        messages = list(request.messages or [])
        unfinished = open_todos(request.state.get("todos") if request.state else None)
        has_summary = any(is_summary_message(m) for m in messages)

        if not unfinished or not has_summary:
            return request, bool((request.state or {}).get("_needs_todo_reseed"))

        if has_pre_compaction_reminder(messages):
            return request, True

        reminder = HumanMessage(content=build_pre_compaction_reminder(unfinished))
        # 插在摘要消息之后，保留近期上下文在后
        insert_at = 0
        for i, m in enumerate(messages):
            if is_summary_message(m):
                insert_at = i + 1
        new_messages = [*messages[:insert_at], reminder, *messages[insert_at:]]
        return request.override(messages=new_messages), True

    def _wrap_response(
        self, response: ModelResponse | ExtendedModelResponse | Any, needs_reseed: bool
    ) -> ModelResponse | ExtendedModelResponse | Any:
        if not needs_reseed:
            return response

        update: dict[str, Any] = {"_needs_todo_reseed": True}
        if isinstance(response, ExtendedModelResponse):
            cmd = response.command
            if cmd is not None and cmd.update:
                update = {**dict(cmd.update), **update}
            return ExtendedModelResponse(
                model_response=response.model_response,
                command=Command(update=update),
            )
        if isinstance(response, ModelResponse):
            return ExtendedModelResponse(
                model_response=response,
                command=Command(update=update),
            )
        return response

    @override
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse | ExtendedModelResponse | Any:
        req, needs = self._maybe_inject(request)
        response = handler(req)
        return self._wrap_response(response, needs)

    @override
    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse | ExtendedModelResponse | Any:
        req, needs = self._maybe_inject(request)
        response = await handler(req)
        return self._wrap_response(response, needs)

    @override
    def before_model(
        self, state: CompactReseedState, runtime: Runtime  # noqa: ARG002
    ) -> dict[str, Any] | None:
        """兜底：state 中已有新 summarization event 时，下一轮 before_model 再注入一次。"""
        event = state.get("_summarization_event")
        key = _event_key(event)
        if key is None:
            return None

        last_key = state.get("_compact_reseed_event_key")
        if last_key == key:
            return None

        unfinished = open_todos(state.get("todos"))  # type: ignore[arg-type]
        if not unfinished:
            return {"_compact_reseed_event_key": key, "_needs_todo_reseed": False}

        messages = state.get("messages") or []
        if has_pre_compaction_reminder(list(messages)):
            return {
                "_compact_reseed_event_key": key,
                "_needs_todo_reseed": True,
            }

        reminder = HumanMessage(content=build_pre_compaction_reminder(unfinished))
        return {
            "messages": [reminder],
            "_needs_todo_reseed": True,
            "_compact_reseed_event_key": key,
        }

    @override
    async def abefore_model(
        self, state: CompactReseedState, runtime: Runtime
    ) -> dict[str, Any] | None:
        return self.before_model(state, runtime)

    def _deny_reseed(self, name: str, call_id: str) -> ToolMessage:
        return ToolMessage(
            content=(
                "[E_TODO_RESEED_REQUIRED] Context was compacted. "
                "Call write_todos first to restore the Pre-Compaction Todo List "
                "before any other tool."
            ),
            tool_call_id=call_id,
            name=name,
            status="error",
        )

    def _after_write_todos(
        self, result: ToolMessage | Command[Any]
    ) -> ToolMessage | Command[Any]:
        if isinstance(result, Command):
            update = dict(result.update or {})
            update["_needs_todo_reseed"] = False
            return Command(
                update=update,
                goto=result.goto,
                resume=result.resume,
                graph=result.graph,
            )
        if isinstance(result, ToolMessage):
            return Command(
                update={
                    "messages": [result],
                    "_needs_todo_reseed": False,
                }
            )
        return Command(update={"_needs_todo_reseed": False})

    @override
    def wrap_tool_call(self, request: Any, handler: Any) -> ToolMessage | Command[Any]:
        state = getattr(request, "state", None) or {}
        tool_call = getattr(request, "tool_call", None) or {}
        if not isinstance(tool_call, dict):
            tool_call = {}
        name = str(tool_call.get("name") or "")
        call_id = str(tool_call.get("id") or "")
        needs = bool(state.get("_needs_todo_reseed"))

        if needs and name != "write_todos":
            return self._deny_reseed(name, call_id)

        result = handler(request)
        if needs and name == "write_todos":
            return self._after_write_todos(result)
        return result

    @override
    async def awrap_tool_call(
        self, request: Any, handler: Any
    ) -> ToolMessage | Command[Any]:
        state = getattr(request, "state", None) or {}
        tool_call = getattr(request, "tool_call", None) or {}
        if not isinstance(tool_call, dict):
            tool_call = {}
        name = str(tool_call.get("name") or "")
        call_id = str(tool_call.get("id") or "")
        needs = bool(state.get("_needs_todo_reseed"))

        if needs and name != "write_todos":
            return self._deny_reseed(name, call_id)

        result = await handler(request)
        if needs and name == "write_todos":
            return self._after_write_todos(result)
        return result
