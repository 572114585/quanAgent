"""工作区 Auto 命令分类矩阵测试。"""
from __future__ import annotations

import pytest

from agent_core.execute_policy import (
    classify_execute_command,
    classify_for_profile,
    execute_profile,
)
from agent_core.permissions import (
    build_interrupt_on,
    is_safe_readonly_shell,
    resolve_permission,
)


@pytest.mark.parametrize(
    "command,effect,reason_substr",
    [
        ("ls -la", "auto", "readonly"),
        ("wc -l foo.txt", "auto", "readonly"),
        ("grep -n pattern file", "auto", "readonly"),
        ("findstr /n pattern file", "auto", "readonly"),
        ("git status", "auto", "git"),
        ("git log --oneline -5", "auto", "git"),
        ("npm run build", "auto", "build"),
        ("pytest -q", "auto", "build"),
        ("python skills/word-docx/scripts/create.py", "auto", "skill"),
        ("python.exe skills\\demo\\scripts\\run.py", "auto", "skill"),
        ("python -c print(1)", "ask", "interpreter"),
        ('python -c "print(1)"', "ask", "interpreter"),
        ('python -c "open(\'/tmp/outline.md\', \'w\').close()"', "ask", "interpreter"),
        ("bash -c 'echo hi'", "ask", "interpreter"),
        (
            "powershell -Command \"(Get-Item 'D:\\project\\file.md').Length\"",
            "ask",
            "interpreter",
        ),
        ("grep pattern file > result.txt", "ask", "redirect"),
        ("pip install requests", "ask", "package"),
        ("npm install lodash", "ask", "package"),
        ("npx cowsay hi", "ask", "npx"),
        ("curl https://example.com", "ask", "network"),
        ("python tmp/myscript.py", "ask", "script"),
        ("rmfile_unknown", "ask", "unknown"),
        ("echo $(whoami)", "deny", "substitution"),
        ("echo `whoami`", "deny", "substitution"),
    ],
)
def test_classify_matrix(command, effect, reason_substr):
    c = classify_execute_command(command)
    assert c.effect == effect, f"{command!r} -> {c.effect}/{c.reason}"
    assert reason_substr in c.reason


def test_chain_takes_highest_risk():
    c = classify_execute_command("ls && python -c '1'")
    assert c.effect == "ask"
    assert "interpreter" in c.reason


def test_manual_profile_upgrades_auto_to_ask(monkeypatch):
    monkeypatch.setenv("EXECUTE_PROFILE", "manual")
    c = classify_for_profile("ls -la")
    assert c.effect == "ask"
    assert c.reason == "manual_profile"


def test_workspace_auto_is_default(monkeypatch):
    monkeypatch.delenv("EXECUTE_PROFILE", raising=False)
    assert execute_profile() == "workspace_auto"


def test_resolve_permission_execute_auto_allows(monkeypatch):
    monkeypatch.delenv("PERMISSION_EXECUTE", raising=False)
    monkeypatch.delenv("EXECUTE_PROFILE", raising=False)
    assert (
        resolve_permission(
            "execute",
            mode="agent",
            entrypoint="web",
            hitl_enabled=True,
            tool_args={"command": "wc -l a.txt"},
        )
        == "allow"
    )
    assert (
        resolve_permission(
            "execute",
            mode="agent",
            entrypoint="web",
            hitl_enabled=True,
            tool_args={"command": "python -c print(1)"},
        )
        == "ask"
    )
    assert (
        resolve_permission(
            "execute",
            mode="agent",
            entrypoint="web",
            hitl_enabled=True,
            tool_args={"command": "echo $(x)"},
        )
        == "deny"
    )


def test_is_safe_readonly_shell_uses_classifier():
    assert is_safe_readonly_shell("git status")
    assert is_safe_readonly_shell("wc -l x")
    assert not is_safe_readonly_shell("python -c print(1)")
    assert not is_safe_readonly_shell("pip install x")


def test_interrupt_on_execute_has_when_predicate(monkeypatch):
    monkeypatch.delenv("PERMISSION_EXECUTE", raising=False)
    interrupt = build_interrupt_on(mode="agent", entrypoint="web", hitl_enabled=True)
    assert interrupt is not None
    assert "execute" in interrupt
    cfg = interrupt["execute"]
    assert isinstance(cfg, dict)
    assert "when" in cfg
    assert callable(cfg["when"])

    class Req:
        def __init__(self, cmd):
            self.tool_call = {"name": "execute", "args": {"command": cmd}, "id": "1"}

    assert cfg["when"](Req("python -c print(1)")) is True
    assert cfg["when"](Req("wc -l x")) is False
