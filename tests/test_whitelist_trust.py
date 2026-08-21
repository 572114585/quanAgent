"""沙箱删除硬拒绝、路径边界与同步/异步执行测试。"""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from sandbox.constants import _SHELL_DENIED_MARKER
from sandbox.trust import execute_trust, get_execute_trust_level
from sandbox.whitelist import _ShellWhitelistFilter


@pytest.fixture
def filter_with_tmp(tmp_path: Path) -> _ShellWhitelistFilter:
    inner = MagicMock()
    inner.cwd = tmp_path
    inner.execute = MagicMock(return_value=MagicMock(output="ok", exit_code=0, truncated=False))
    inner.aexecute = AsyncMock(return_value=MagicMock(output="ok", exit_code=0, truncated=False))
    return _ShellWhitelistFilter(inner, skills_root=str(tmp_path))


def test_trust_context_default_strict() -> None:
    assert get_execute_trust_level() == "strict"
    with execute_trust("hitl_approved"):
        assert get_execute_trust_level() == "hitl_approved"
    assert get_execute_trust_level() == "strict"


@pytest.mark.parametrize(
    "command",
    [
        "rm -rf output/project",
        "Remove-Item output/project",
        "git clean -fd",
        "npm uninstall package",
        "find . -delete",
    ],
)
@pytest.mark.parametrize("trust_level", ["strict", "hitl_approved"])
def test_delete_is_rejected_for_all_trust_levels(
    filter_with_tmp: _ShellWhitelistFilter, command: str, trust_level: str
) -> None:
    response = filter_with_tmp._reject_if_disallowed(command, trust_level=trust_level)
    assert response is not None
    assert _SHELL_DENIED_MARKER in response.output
    assert "删除" in response.output


def test_non_delete_commands_bypass_old_soft_policy(
    filter_with_tmp: _ShellWhitelistFilter,
) -> None:
    for command in (
        "pip install package",
        "python -c print(1)",
        "curl https://example.com",
        "unknown-command --flag",
        "echo $(whoami)",
    ):
        assert filter_with_tmp._reject_if_disallowed(command, trust_level="strict") is None


def test_cd_out_of_sandbox_is_still_rejected(
    filter_with_tmp: _ShellWhitelistFilter,
) -> None:
    response = filter_with_tmp._reject_if_disallowed("cd ..", trust_level="hitl_approved")
    assert response is not None
    assert "超出工作目录" in response.output or "拦截" in response.output


def test_execute_does_not_call_inner_for_delete(
    filter_with_tmp: _ShellWhitelistFilter,
) -> None:
    response = filter_with_tmp.execute("rm output/a.txt")
    assert _SHELL_DENIED_MARKER in response.output
    filter_with_tmp._backend.execute.assert_not_called()


def test_execute_calls_inner_for_non_delete(
    filter_with_tmp: _ShellWhitelistFilter,
) -> None:
    response = filter_with_tmp.execute("pip install package")
    assert response.output == "ok"
    filter_with_tmp._backend.execute.assert_called_once_with(
        "pip install package", timeout=None
    )


def test_aexecute_has_same_delete_boundary(
    filter_with_tmp: _ShellWhitelistFilter,
) -> None:
    async def run() -> None:
        response = await filter_with_tmp.aexecute("rm output/a.txt")
        assert _SHELL_DENIED_MARKER in response.output
        filter_with_tmp._backend.aexecute.assert_not_called()

        response = await filter_with_tmp.aexecute("python -c print(1)")
        assert response.output == "ok"
        filter_with_tmp._backend.aexecute.assert_awaited_once_with(
            "python -c print(1)", timeout=None
        )

    asyncio.run(run())


def test_hooks_keep_delete_as_strict() -> None:
    from hooks import HooksMiddleware, HooksRuntime

    runtime = HooksRuntime(
        mode="agent",
        entrypoint="web",
        hitl_enabled=True,
        interrupt_on=frozenset({"execute"}),
    )
    middleware = HooksMiddleware(runtime)
    assert middleware._execute_trust_level(
        "execute", {"command": "rm output/a.txt"}
    ) == "strict"
    assert middleware._execute_trust_level(
        "execute", {"command": "python -c print(1)"}
    ) == "strict"
