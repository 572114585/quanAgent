"""Hooks middleware 单测。"""
from langchain_core.messages import ToolMessage

from agent_core.permissions import deny_message
from hooks import HookContext, HookDecision, HookRegistration, HooksRuntime


def test_hooks_runtime_denies_execute_in_plan_mode():
    rt = HooksRuntime(mode="plan", entrypoint="web", hitl_enabled=False)
    ctx = HookContext(
        event="before_tool",
        tool_name="execute",
        tool_args={"command": "ls"},
        tool_call_id="tc1",
        mode="plan",
        entrypoint="web",
    )
    decision = rt.run_before(ctx)
    assert decision.action == "deny"
    assert "Plan" in decision.message or "E_PERMISSION_DENIED" in decision.message


def test_hooks_runtime_allows_read_in_plan_mode():
    rt = HooksRuntime(mode="plan", entrypoint="web", hitl_enabled=False)
    ctx = HookContext(
        event="before_tool",
        tool_name="read_file",
        tool_args={"path": "skills/x/SKILL.md"},
        tool_call_id="tc2",
        mode="plan",
        entrypoint="web",
    )
    assert rt.run_before(ctx).action == "allow"


def test_script_hook_can_deny():
    def before(ctx: HookContext):
        if ctx.tool_name == "execute":
            return HookDecision(action="deny", message="blocked by test hook")
        return None

    rt = HooksRuntime(
        mode="agent",
        entrypoint="cli",
        hitl_enabled=False,
        always_approve=True,
        registrations=[HookRegistration(name="test", before_tool=before)],
    )
    ctx = HookContext(
        event="before_tool",
        tool_name="execute",
        tool_args={},
        tool_call_id="tc3",
        mode="agent",
        entrypoint="cli",
    )
    decision = rt.run_before(ctx)
    assert decision.action == "deny"
    assert "test hook" in decision.message


def test_deny_message_channel():
    msg = deny_message("execute", mode="agent", entrypoint="channel")
    assert "E_PERMISSION_DENIED" in msg
    assert "渠道" in msg


def test_unknown_tool_denied_by_hooks():
    rt = HooksRuntime(mode="agent", entrypoint="web", hitl_enabled=True)
    ctx = HookContext(
        event="before_tool",
        tool_name="shadow_exfiltrate",
        tool_args={},
        tool_call_id="tc-unk",
        mode="agent",
        entrypoint="web",
    )
    decision = rt.run_before(ctx)
    assert decision.action == "deny"
    assert "E_PERMISSION_DENIED" in decision.message


def test_explicit_ask_without_interrupt_on_is_denied(monkeypatch):
    """显式 PERMISSION_EXECUTE=ask 但未登记 interrupt_on → fail-closed。"""
    monkeypatch.setenv("PERMISSION_EXECUTE", "ask")
    rt = HooksRuntime(
        mode="agent",
        entrypoint="web",
        hitl_enabled=True,
        interrupt_on=frozenset(),  # 故意不挂 execute
    )
    ctx = HookContext(
        event="before_tool",
        tool_name="execute",
        tool_args={"command": "pip install x"},
        tool_call_id="tc-ask",
        mode="agent",
        entrypoint="web",
    )
    decision = rt.run_before(ctx)
    assert decision.action == "deny"
    assert "ask 未挂 HITL" in decision.message


def test_ask_with_interrupt_on_allows_after_hitl():
    rt = HooksRuntime(
        mode="agent",
        entrypoint="web",
        hitl_enabled=True,
        interrupt_on=frozenset({"execute"}),
    )
    ctx = HookContext(
        event="before_tool",
        tool_name="execute",
        tool_args={"command": "ls"},
        tool_call_id="tc-ok",
        mode="agent",
        entrypoint="web",
    )
    assert rt.run_before(ctx).action == "allow"


def test_middleware_wrap_returns_tool_message():
    from hooks import HooksMiddleware

    rt = HooksRuntime(mode="plan", entrypoint="web", hitl_enabled=False)
    mw = HooksMiddleware(rt)

    class Req:
        tool_call = {"name": "execute", "args": {"command": "echo hi"}, "id": "id1"}

    called = {"n": 0}

    def handler(_req):
        called["n"] += 1
        return ToolMessage(content="ok", tool_call_id="id1", name="execute")

    result = mw.wrap_tool_call(Req(), handler)
    assert isinstance(result, ToolMessage)
    assert result.status == "error"
    assert called["n"] == 0
