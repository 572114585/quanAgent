"""子智能体 Hooks 注入与 approve 后 soft bypass 集成测试。"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from agent_core.permissions import build_interrupt_on
from hooks import HooksMiddleware, HooksRuntime, build_hooks_middleware
from sandbox.constants import _SHELL_DENIED_MARKER
from sandbox.trust import get_execute_trust_level
from sandbox.whitelist import _ShellWhitelistFilter


def test_subagent_with_hooks_injects_middleware():
    from agent_core.runtime import _subagent_with_hooks

    hooks = MagicMock()
    interrupt = {"execute": {"allowed_decisions": ["approve", "reject"]}}
    spec = {"name": "research-agent", "tools": [], "system_prompt": "x"}
    out = _subagent_with_hooks(spec, hooks, interrupt_on=interrupt)
    assert out["middleware"][0] is hooks
    assert out["interrupt_on"] is interrupt
    # 原 spec 不被就地修改
    assert "middleware" not in spec


def test_build_hooks_middleware_registers_dict_interrupt_on():
    interrupt = build_interrupt_on(mode="agent", entrypoint="web", hitl_enabled=True)
    mw = build_hooks_middleware(
        mode="agent",
        entrypoint="web",
        hitl_enabled=True,
        interrupt_on=interrupt,
    )
    assert "execute" in mw.runtime.interrupt_on


@pytest.mark.asyncio
async def test_wrap_tool_call_sets_hitl_trust_for_python_c(tmp_path: Path):
    """子图同款 Hooks：批准后的 python -c 以 hitl_approved 执行。"""
    inner = MagicMock()
    inner.cwd = tmp_path
    called = {"trust": None}

    async def _aexecute(command, *, timeout=None):
        called["trust"] = get_execute_trust_level()
        return MagicMock(output="ok", exit_code=0, truncated=False)

    inner.aexecute = _aexecute
    filt = _ShellWhitelistFilter(
        inner,
        allow_commands={"python", "python3", "ls"},
        skills_root=str(tmp_path),
    )

    runtime = HooksRuntime(
        mode="agent",
        entrypoint="web",
        hitl_enabled=True,
        interrupt_on=frozenset({"execute"}),
    )
    mw = HooksMiddleware(runtime)

    class Req:
        tool_call = {
            "name": "execute",
            "args": {"command": "python -c print(1)"},
            "id": "tc1",
        }

    async def handler(_req):
        # 模拟 FilesystemMiddleware → backend.aexecute
        return await filt.aexecute("python -c print(1)")

    result = await mw.awrap_tool_call(Req(), handler)
    assert called["trust"] == "hitl_approved"
    assert getattr(result, "exit_code", 0) == 0
    assert _SHELL_DENIED_MARKER not in str(getattr(result, "output", ""))


@pytest.mark.asyncio
async def test_auto_wc_runs_without_hitl_trust(tmp_path: Path):
    """wc 等 auto 命令：strict trust 下 whitelist 仍放行。"""
    inner = MagicMock()
    inner.cwd = tmp_path

    async def _aexecute(command, *, timeout=None):
        assert get_execute_trust_level() == "strict"
        return MagicMock(output="3", exit_code=0, truncated=False)

    inner.aexecute = _aexecute
    # allow 不含 wc，依赖 classification auto
    filt = _ShellWhitelistFilter(
        inner,
        allow_commands={"python", "ls"},
        skills_root=str(tmp_path),
    )
    runtime = HooksRuntime(
        mode="agent",
        entrypoint="web",
        hitl_enabled=True,
        interrupt_on=frozenset({"execute"}),
    )
    mw = HooksMiddleware(runtime)

    class Req:
        tool_call = {
            "name": "execute",
            "args": {"command": "wc -l foo"},
            "id": "tc2",
        }

    async def handler(_req):
        return await filt.aexecute("wc -l foo")

    result = await mw.awrap_tool_call(Req(), handler)
    assert getattr(result, "exit_code", 1) == 0


def test_hard_deny_still_blocks_after_hitl(tmp_path: Path):
    inner = MagicMock()
    inner.cwd = tmp_path
    filt = _ShellWhitelistFilter(inner, allow_commands={"echo"}, skills_root=str(tmp_path))
    resp = filt._reject_if_disallowed("echo $(whoami)", trust_level="hitl_approved")
    assert resp is not None
    assert "命令替换" in resp.output
