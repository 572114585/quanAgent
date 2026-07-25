"""权限矩阵单测。"""
from agent_core.permissions import build_interrupt_on, resolve_permission


def test_plan_mode_denies_write_and_execute():
    assert resolve_permission("execute", mode="plan") == "deny"
    assert resolve_permission("write_file", mode="plan") == "deny"
    assert resolve_permission("edit_file", mode="plan") == "deny"
    assert resolve_permission("replace_file", mode="plan") == "deny"
    assert resolve_permission("read_file", mode="plan") == "allow"
    assert resolve_permission("inspect_file", mode="plan") == "allow"
    assert resolve_permission("check_research_material", mode="plan") == "allow"
    assert resolve_permission("write_todos", mode="plan") == "allow"
    assert build_interrupt_on(mode="plan", hitl_enabled=True) is None


def test_channel_denies_execute_and_write():
    assert resolve_permission("execute", entrypoint="channel") == "deny"
    assert resolve_permission("write_file", entrypoint="channel") == "deny"
    assert resolve_permission("replace_file", entrypoint="channel") == "deny"
    assert resolve_permission("read_file", entrypoint="channel") == "allow"
    assert resolve_permission("inspect_file", entrypoint="channel") == "allow"
    assert build_interrupt_on(entrypoint="channel", hitl_enabled=False) is None


def test_agent_hitl_asks_execute_allows_write(monkeypatch):
    """workspace_auto：execute 工具级 ask（when 细分），write/edit 默认放行。"""
    monkeypatch.delenv("PERMISSION_EXECUTE", raising=False)
    monkeypatch.delenv("PERMISSION_WRITE", raising=False)
    monkeypatch.delenv("EXECUTE_PROFILE", raising=False)
    assert resolve_permission("execute", mode="agent", entrypoint="web", hitl_enabled=True) == "ask"
    assert resolve_permission("write_file", mode="agent", entrypoint="web", hitl_enabled=True) == "allow"
    assert resolve_permission("edit_file", mode="agent", entrypoint="web", hitl_enabled=True) == "allow"
    assert resolve_permission("replace_file", mode="agent", entrypoint="web", hitl_enabled=True) == "allow"
    assert resolve_permission("inspect_file", mode="agent", entrypoint="web", hitl_enabled=True) == "allow"
    interrupt = build_interrupt_on(mode="agent", entrypoint="web", hitl_enabled=True)
    assert interrupt is not None
    assert "execute" in interrupt
    assert isinstance(interrupt["execute"], dict)
    assert callable(interrupt["execute"].get("when"))
    assert "write_file" not in interrupt
    assert "edit_file" not in interrupt
    assert "replace_file" not in interrupt


def test_safe_readonly_shell_helper(monkeypatch):
    from agent_core.permissions import is_safe_readonly_shell

    monkeypatch.delenv("EXECUTE_PROFILE", raising=False)
    assert is_safe_readonly_shell("ls -la")
    assert is_safe_readonly_shell("git status && pwd")
    assert not is_safe_readonly_shell("echo $(whoami)")
    assert not is_safe_readonly_shell("python script.py")
    # 安全命令按分类 auto → allow，不再一律 ask
    assert (
        resolve_permission(
            "execute",
            mode="agent",
            entrypoint="web",
            hitl_enabled=True,
            tool_args={"command": "git status"},
        )
        == "allow"
    )


def test_always_approve_turns_ask_into_allow(monkeypatch):
    monkeypatch.delenv("PERMISSION_EXECUTE", raising=False)
    assert (
        resolve_permission(
            "execute",
            mode="agent",
            entrypoint="cli",
            hitl_enabled=True,
            always_approve=True,
        )
        == "allow"
    )
    assert (
        build_interrupt_on(
            mode="agent",
            entrypoint="cli",
            hitl_enabled=True,
            always_approve=True,
        )
        is None
    )


def test_env_permission_execute_deny(monkeypatch):
    monkeypatch.setenv("PERMISSION_EXECUTE", "deny")
    assert resolve_permission("execute", mode="agent", hitl_enabled=True) == "deny"


def test_env_permission_write_ask(monkeypatch):
    monkeypatch.setenv("PERMISSION_WRITE", "ask")
    assert resolve_permission("write_file", mode="agent", hitl_enabled=True) == "ask"
    interrupt = build_interrupt_on(mode="agent", entrypoint="web", hitl_enabled=True)
    assert interrupt is not None
    assert interrupt.get("write_file") is True
    assert interrupt.get("replace_file") is True


def test_unknown_tool_is_denied():
    assert resolve_permission("totally_unknown_tool", mode="agent", hitl_enabled=True) == "deny"
    assert resolve_permission("totally_unknown_tool", mode="agent", hitl_enabled=False) == "deny"
    assert resolve_permission("totally_unknown_tool", mode="plan") == "deny"
