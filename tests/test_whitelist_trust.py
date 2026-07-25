"""沙盒硬/软拒绝与 HITL 信任级别单测。"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from sandbox.constants import _SHELL_DENIED_MARKER
from sandbox.trust import execute_trust, get_execute_trust_level
from sandbox.whitelist import _ShellWhitelistFilter


@pytest.fixture
def filter_with_tmp(tmp_path: Path) -> _ShellWhitelistFilter:
    """不连真实 shell：内层 mock，只测拦截逻辑。"""
    inner = MagicMock()
    inner.cwd = tmp_path
    inner.execute = MagicMock(
        return_value=MagicMock(output="ok", exit_code=0, truncated=False)
    )

    async def _aexecute(command, *, timeout=None):
        return MagicMock(output="ok", exit_code=0, truncated=False)

    inner.aexecute = _aexecute
    # skills 白名单非空，便于测 python_script_not_allowed
    skills = tmp_path / "skills" / "demo" / "scripts"
    skills.mkdir(parents=True)
    (skills / "run.py").write_text("# skill\n", encoding="utf-8")
    return _ShellWhitelistFilter(
        inner,
        allow_commands={"python", "python3", "ls", "echo", "cd", "curl", "bash", "sh"},
        skills_root=str(tmp_path),
    )


def test_trust_context_default_strict():
    assert get_execute_trust_level() == "strict"
    with execute_trust("hitl_approved"):
        assert get_execute_trust_level() == "hitl_approved"
    assert get_execute_trust_level() == "strict"


def test_strict_rejects_not_in_allowlist(filter_with_tmp: _ShellWhitelistFilter):
    resp = filter_with_tmp._reject_if_disallowed("pip install foo", trust_level="strict")
    assert resp is not None
    assert _SHELL_DENIED_MARKER in resp.output
    assert "pip" in resp.output


def test_hitl_approved_bypasses_soft_allowlist(filter_with_tmp: _ShellWhitelistFilter):
    resp = filter_with_tmp._reject_if_disallowed("pip install foo", trust_level="hitl_approved")
    assert resp is None


def test_hitl_approved_bypasses_python_script_whitelist(filter_with_tmp: _ShellWhitelistFilter):
    resp = filter_with_tmp._reject_if_disallowed(
        "python tmp/myscript.py", trust_level="hitl_approved"
    )
    assert resp is None

    strict = filter_with_tmp._reject_if_disallowed(
        "python tmp/myscript.py", trust_level="strict"
    )
    assert strict is not None
    assert "python_script" in strict.output or "白名单" in strict.output


def test_hitl_approved_still_rejects_command_substitution(filter_with_tmp: _ShellWhitelistFilter):
    resp = filter_with_tmp._reject_if_disallowed(
        "echo $(whoami)", trust_level="hitl_approved"
    )
    assert resp is not None
    assert "命令替换" in resp.output


def test_hitl_approved_still_rejects_hard_deny(filter_with_tmp: _ShellWhitelistFilter):
    resp = filter_with_tmp._reject_if_disallowed("rm -rf /", trust_level="hitl_approved")
    assert resp is not None
    assert "硬拒绝" in resp.output


def test_hitl_approved_still_rejects_cd_out_of_sandbox(filter_with_tmp: _ShellWhitelistFilter):
    # 相对 .. 会解析到 workspace 外；真绝对盘符（非 C: 被改写吞掉的情况）也测越界
    resp = filter_with_tmp._reject_if_disallowed("cd ..", trust_level="hitl_approved")
    assert resp is not None
    assert "超出工作目录" in resp.output or "拦截" in resp.output


def test_execute_reads_contextvar(filter_with_tmp: _ShellWhitelistFilter):
    # strict：pip 被拒，不调用内层
    out = filter_with_tmp.execute("pip install x")
    assert _SHELL_DENIED_MARKER in out.output
    filter_with_tmp._backend.execute.assert_not_called()

    with execute_trust("hitl_approved"):
        out2 = filter_with_tmp.execute("pip install x")
    assert out2.exit_code == 0
    filter_with_tmp._backend.execute.assert_called_once()


def test_hooks_sets_hitl_trust_for_ask_execute():
    from hooks import HooksMiddleware, HooksRuntime

    runtime = HooksRuntime(
        mode="agent",
        entrypoint="web",
        hitl_enabled=True,
        always_approve=False,
        interrupt_on=frozenset({"execute"}),
    )
    mw = HooksMiddleware(runtime)
    # ask 类命令到达 wrap → hitl_approved
    assert (
        mw._execute_trust_level("execute", {"command": "python -c print(1)"})
        == "hitl_approved"
    )
    # auto 类保持 strict（whitelist 按 classification 跳过软层）
    assert mw._execute_trust_level("execute", {"command": "wc -l x"}) == "strict"
    assert mw._execute_trust_level("read_file") == "strict"
    assert mw._execute_trust_level("task") == "strict"


def test_auto_command_skips_soft_without_hitl_trust(filter_with_tmp):
    """workspace_auto：wc/grep 等 auto 命令在 strict trust 下也应跳过软白名单。"""
    # filter 的 allow 不含 wc，但 classification=auto 应放行
    resp = filter_with_tmp._reject_if_disallowed("wc -l foo", trust_level="strict")
    assert resp is None


def test_hitl_approved_bypasses_python_c(filter_with_tmp):
    resp = filter_with_tmp._reject_if_disallowed(
        "python -c print(1)", trust_level="hitl_approved"
    )
    assert resp is None
    strict = filter_with_tmp._reject_if_disallowed(
        "python -c print(1)", trust_level="strict"
    )
    assert strict is not None
    assert _SHELL_DENIED_MARKER in strict.output


def test_hooks_always_approve_sets_hitl_trust():
    from hooks import HooksMiddleware, HooksRuntime

    runtime = HooksRuntime(
        mode="agent",
        entrypoint="cli",
        hitl_enabled=False,
        always_approve=True,
    )
    mw = HooksMiddleware(runtime)
    assert mw._execute_trust_level("execute", {"command": "pip install x"}) == "hitl_approved"
    assert mw._execute_trust_level("task") == "hitl_approved"


def test_hooks_allow_without_hitl_stays_strict(monkeypatch):
    from hooks import HooksMiddleware, HooksRuntime

    monkeypatch.setenv("PERMISSION_EXECUTE", "allow")
    runtime = HooksRuntime(
        mode="agent",
        entrypoint="web",
        hitl_enabled=True,
        always_approve=False,
        interrupt_on=frozenset(),  # allow → 不挂 interrupt
    )
    mw = HooksMiddleware(runtime)
    # 无 interrupt_on → strict（即使命令是 ask 类）
    assert mw._execute_trust_level("execute", {"command": "pip install x"}) == "strict"


def test_hooks_task_without_hitl_stays_strict():
    from hooks import HooksMiddleware, HooksRuntime

    runtime = HooksRuntime(
        mode="agent",
        entrypoint="channel",
        hitl_enabled=False,
        always_approve=False,
    )
    mw = HooksMiddleware(runtime)
    assert mw._execute_trust_level("task") == "strict"
