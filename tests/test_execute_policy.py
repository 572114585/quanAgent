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
    "command",
    [
        "rm -f output/a.txt",
        "rmdir tmp/project",
        "unlink output/a.txt",
        "Remove-Item output/a.txt",
        "del output\\a.txt",
        "find . -name '*.tmp' -delete",
        "find . -exec rm {} \\;",
        "git clean -fd",
        "npm uninstall lodash",
        "pip uninstall requests",
        "docker rm container",
        "kubectl delete pod demo",
        "sh -c 'rm output/a.txt'",
        "cmd /c del output\\a.txt",
        "sudo rm output/a.txt",
        "echo $(rm output/a.txt)",
        "echo `rm output/a.txt`",
    ],
)
def test_delete_commands_are_hard_denied(command: str) -> None:
    classification = classify_execute_command(command)
    assert classification.effect == "deny"
    assert classification.reason == "delete_command"


@pytest.mark.parametrize(
    "command",
    [
        "ls -la",
        "unknown_tool --flag",
        "curl https://example.com",
        "pip install requests",
        "python -c print(1)",
        "bash -c 'echo hi'",
        "grep pattern file > result.txt",
        "echo $(whoami)",
        "echo `whoami`",
        "echo rm is only text",
        "rmfile_unknown",
    ],
)
def test_non_delete_commands_are_auto(command: str) -> None:
    classification = classify_execute_command(command)
    assert classification.effect == "auto", (command, classification)
    assert classification.reason == "allowed_command"


def test_chain_with_delete_is_denied() -> None:
    classification = classify_execute_command("echo preparing && rm output/a.txt")
    assert classification.effect == "deny"
    assert classification.reason == "delete_command"


def test_manual_profile_only_asks_for_non_delete(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXECUTE_PROFILE", "manual")
    assert classify_for_profile("ls -la").effect == "ask"
    assert classify_for_profile("rm output/a.txt").effect == "deny"


def test_workspace_auto_is_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EXECUTE_PROFILE", raising=False)
    assert execute_profile() == "workspace_auto"


def test_default_execute_permission_allows_non_delete(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PERMISSION_EXECUTE", raising=False)
    monkeypatch.delenv("EXECUTE_PROFILE", raising=False)
    for command in ("wc -l a.txt", "python -c print(1)", "pip install x"):
        assert resolve_permission(
            "execute",
            mode="agent",
            entrypoint="web",
            hitl_enabled=True,
            tool_args={"command": command},
        ) == "allow"


@pytest.mark.parametrize("permission", ["allow", "ask", "deny"])
def test_delete_permission_overrides_environment(
    monkeypatch: pytest.MonkeyPatch, permission: str
) -> None:
    monkeypatch.setenv("PERMISSION_EXECUTE", permission)
    assert resolve_permission(
        "execute",
        mode="agent",
        entrypoint="web",
        hitl_enabled=True,
        always_approve=True,
        tool_args={"command": "rm output/a.txt"},
    ) == "deny"


def test_explicit_ask_still_interrupts_non_delete(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PERMISSION_EXECUTE", "ask")
    interrupt = build_interrupt_on(mode="agent", entrypoint="web", hitl_enabled=True)
    assert interrupt is not None
    predicate = interrupt["execute"]["when"]

    class Request:
        tool_call = {"name": "execute", "args": {"command": "curl https://example.com"}}

    assert predicate(Request()) is True


def test_delete_does_not_interrupt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PERMISSION_EXECUTE", "ask")
    interrupt = build_interrupt_on(mode="agent", entrypoint="web", hitl_enabled=True)
    assert interrupt is not None
    predicate = interrupt["execute"]["when"]

    class Request:
        tool_call = {"name": "execute", "args": {"command": "rm output/a.txt"}}

    assert predicate(Request()) is False


def test_is_safe_readonly_shell_is_compatibility_helper() -> None:
    assert is_safe_readonly_shell("git status")
    assert is_safe_readonly_shell("python -c print(1)")
    assert not is_safe_readonly_shell("rm output/a.txt")
