"""TodoGate / CompactReseed / 任务纪律相关单测。"""
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.types import Command

from agent_core.middleware.compact_reseed import (
    CompactReseedMiddleware,
    build_pre_compaction_reminder,
    has_pre_compaction_reminder,
    is_summary_message,
)
from agent_core.middleware.todo_gate import (
    TodoGateMiddleware,
    build_todo_gate_reminder,
    format_open_todos,
    open_todos,
)
from agent_core.prompts import SYSTEM_PROMPT, system_prompt_for
from hooks import (
    BlindRetryTracker,
    HookContext,
    HooksRuntime,
    builtin_anti_blind_retry,
    reset_blind_retry_tracker,
)


def test_open_todos_filters_completed():
    todos = [
        {"content": "a", "status": "pending"},
        {"content": "b", "status": "in_progress"},
        {"content": "c", "status": "completed"},
    ]
    unfinished = open_todos(todos)
    assert len(unfinished) == 2
    assert format_open_todos(unfinished).count("- [") == 2


def test_todo_gate_jumps_when_ending_with_open_todos():
    mw = TodoGateMiddleware(max_nudges=3)
    state = {
        "messages": [AIMessage(content="先到这里，要继续吗？")],
        "todos": [
            {"content": "检索资料", "status": "in_progress"},
            {"content": "写大纲", "status": "pending"},
        ],
        "_todo_gate_nudges": 0,
    }
    update = mw.after_model(state, runtime=None)  # type: ignore[arg-type]
    assert update is not None
    assert update["jump_to"] == "model"
    assert update["_todo_gate_nudges"] == 1
    assert isinstance(update["messages"][0], HumanMessage)
    assert "End-of-turn Todo Gate" in update["messages"][0].content


def test_todo_gate_allows_tool_calls_and_resets_nudges():
    mw = TodoGateMiddleware()
    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[{"name": "read_file", "args": {"path": "x"}, "id": "1", "type": "tool_call"}],
            )
        ],
        "todos": [{"content": "a", "status": "pending"}],
        "_todo_gate_nudges": 2,
    }
    update = mw.after_model(state, runtime=None)  # type: ignore[arg-type]
    assert update == {"_todo_gate_nudges": 0}


def test_todo_gate_allows_end_when_todos_done():
    mw = TodoGateMiddleware()
    state = {
        "messages": [AIMessage(content="全部完成")],
        "todos": [{"content": "a", "status": "completed"}],
    }
    assert mw.after_model(state, runtime=None) is None  # type: ignore[arg-type]


def test_todo_gate_stops_after_max_nudges():
    mw = TodoGateMiddleware(max_nudges=2)
    state = {
        "messages": [AIMessage(content="又停了")],
        "todos": [{"content": "a", "status": "pending"}],
        "_todo_gate_nudges": 2,
    }
    update = mw.after_model(state, runtime=None)  # type: ignore[arg-type]
    assert update == {"_todo_gate_nudges": 0}


def test_build_todo_gate_reminder_lists_items():
    text = build_todo_gate_reminder([{"content": "写报告", "status": "pending"}])
    assert "写报告" in text
    assert "Do not ask the user whether to continue" in text


def test_compact_reseed_injects_on_summary_messages():
    mw = CompactReseedMiddleware()
    summary = HumanMessage(
        content="## Summary\nDid research.",
        additional_kwargs={"lc_source": "summarization"},
    )
    assert is_summary_message(summary)

    class Req:
        messages = [summary, HumanMessage(content="recent")]
        state = {
            "todos": [{"content": "继续写第2节", "status": "pending"}],
        }

        def override(self, **kwargs):
            r = Req()
            r.messages = kwargs.get("messages", self.messages)
            r.state = self.state
            r.override = self.override
            return r

    req, needs = mw._maybe_inject(Req())  # noqa: SLF001
    assert needs is True
    assert has_pre_compaction_reminder(req.messages)
    assert "Pre-Compaction Todo List" in req.messages[1].content


def test_compact_reseed_blocks_non_write_todos():
    mw = CompactReseedMiddleware()

    class Req:
        state = {"_needs_todo_reseed": True}
        tool_call = {"name": "web_search", "args": {"query": "x"}, "id": "tc1"}

    called = {"n": 0}

    def handler(_req):
        called["n"] += 1
        return ToolMessage(content="ok", tool_call_id="tc1", name="web_search")

    result = mw.wrap_tool_call(Req(), handler)
    assert isinstance(result, ToolMessage)
    assert result.status == "error"
    assert "E_TODO_RESEED_REQUIRED" in result.content
    assert called["n"] == 0


def test_compact_reseed_clears_flag_after_write_todos():
    mw = CompactReseedMiddleware()

    class Req:
        state = {"_needs_todo_reseed": True}
        tool_call = {
            "name": "write_todos",
            "args": {"todos": [{"content": "a", "status": "pending"}]},
            "id": "tc2",
        }

    def handler(_req):
        return ToolMessage(content="updated", tool_call_id="tc2", name="write_todos")

    result = mw.wrap_tool_call(Req(), handler)
    assert isinstance(result, Command)
    assert result.update.get("_needs_todo_reseed") is False


def test_anti_blind_retry_denies_third_identical_call():
    reset_blind_retry_tracker()
    tracker = BlindRetryTracker(max_consecutive=3)
    reg = builtin_anti_blind_retry(max_consecutive=3, tracker=tracker)
    rt = HooksRuntime(
        mode="agent",
        entrypoint="web",
        hitl_enabled=True,
        always_approve=True,
        registrations=[reg],
    )

    def ctx(result=None):
        return HookContext(
            event="before_tool" if result is None else "after_tool",
            tool_name="web_search",
            tool_args={"query": "same"},
            tool_call_id="x",
            mode="agent",
            entrypoint="web",
            result=result,
        )

    fail = ToolMessage(content="[E_TEST] fail", tool_call_id="x", name="web_search", status="error")
    assert rt.run_before(ctx()).action == "allow"
    rt.run_after(ctx(fail))
    assert rt.run_before(ctx()).action == "allow"
    rt.run_after(ctx(fail))
    decision = rt.run_before(ctx())
    assert decision.action == "deny"
    assert "E_BLIND_RETRY" in decision.message


def test_anti_blind_retry_resets_on_success():
    tracker = BlindRetryTracker(max_consecutive=3)
    reg = builtin_anti_blind_retry(max_consecutive=3, tracker=tracker)
    rt = HooksRuntime(
        mode="agent",
        entrypoint="web",
        hitl_enabled=True,
        always_approve=True,
        registrations=[reg],
    )
    fail = ToolMessage(content="boom", tool_call_id="x", name="web_search", status="error")
    ok = ToolMessage(content="ok", tool_call_id="x", name="web_search")

    def before():
        return rt.run_before(
            HookContext(
                event="before_tool",
                tool_name="web_search",
                tool_args={"query": "same"},
                tool_call_id="x",
                mode="agent",
                entrypoint="web",
            )
        )

    def after(result):
        rt.run_after(
            HookContext(
                event="after_tool",
                tool_name="web_search",
                tool_args={"query": "same"},
                tool_call_id="x",
                mode="agent",
                entrypoint="web",
                result=result,
            )
        )

    # 失败 1 次后成功 → streak 清零
    assert before().action == "allow"
    after(fail)
    assert before().action == "allow"
    after(ok)
    # 再连续失败 2 次后，第 3 次 before 才 deny
    assert before().action == "allow"
    after(fail)
    assert before().action == "allow"
    after(fail)
    assert before().action == "deny"


def test_anti_blind_retry_allows_different_args():
    tracker = BlindRetryTracker(max_consecutive=3)
    reg = builtin_anti_blind_retry(max_consecutive=3, tracker=tracker)
    rt = HooksRuntime(
        mode="agent",
        entrypoint="cli",
        hitl_enabled=False,
        always_approve=True,
        registrations=[reg],
    )
    for q in ("a", "a", "b", "b"):
        d = rt.run_before(
            HookContext(
                event="before_tool",
                tool_name="web_search",
                tool_args={"query": q},
                tool_call_id="x",
                mode="agent",
                entrypoint="cli",
            )
        )
        assert d.action == "allow"


def test_prompts_include_task_completion_discipline():
    assert "任务完成纪律" in SYSTEM_PROMPT
    assert "不要半路请示继续" in SYSTEM_PROMPT
    assert "完成前验证" in SYSTEM_PROMPT
    assert "Plan 使用边界" in SYSTEM_PROMPT
    assert "仅真歧义时规划" in SYSTEM_PROMPT
    plan = system_prompt_for("plan")
    assert "仅用于有真歧义的任务" in plan


def test_pre_compaction_reminder_format():
    text = build_pre_compaction_reminder([{"content": "写第3节", "status": "in_progress"}])
    assert "Pre-Compaction Todo List" in text
    assert "写第3节" in text
