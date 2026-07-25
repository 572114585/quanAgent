"""RunRegistry / resume 校验 / 协议层单测。"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from agent_core.run_registry import RunConflictError, RunRegistry, reset_run_registry_for_tests
from tools.ask_user_question import (
    ResumeValidationError,
    action_hash,
    collect_interrupt_groups,
    validate_resume_against_state,
)


def test_action_hash_stable():
    a = action_hash("execute", {"command": "ls"})
    b = action_hash("execute", {"command": "ls"})
    c = action_hash("execute", {"command": "pwd"})
    assert a == b
    assert a != c


def test_validate_resume_rejects_empty_and_stale():
    state = SimpleNamespace(tasks=[])
    with pytest.raises(ResumeValidationError) as ei:
        validate_resume_against_state(state, [])
    assert ei.value.status_code == 409

    intr = SimpleNamespace(
        id="i1",
        value={
            "action_requests": [{"name": "execute", "args": {"command": "ls"}}],
        },
    )
    task = SimpleNamespace(interrupts=[intr])
    state = SimpleNamespace(tasks=[task])
    groups = collect_interrupt_groups(state)
    assert groups[0]["kind"] == "tool_approval"
    assert groups[0]["actionHash"]

    with pytest.raises(ResumeValidationError) as e2:
        validate_resume_against_state(
            state,
            [{"interruptId": "missing", "decisions": [{"type": "approve"}]}],
        )
    assert e2.value.status_code == 409

    with pytest.raises(ResumeValidationError):
        validate_resume_against_state(
            state,
            [{"interruptId": "i1", "decisions": []}],
        )

    ok = validate_resume_against_state(
        state,
        [
            {
                "interruptId": "i1",
                "kind": "tool_approval",
                "decisions": [{"type": "approve"}],
                "actionHash": groups[0]["actionHash"],
            }
        ],
    )
    assert "i1" in ok


def test_validate_resume_rejects_action_hash_mismatch():
    intr = SimpleNamespace(
        id="i1",
        value={"action_requests": [{"name": "execute", "args": {"command": "pip install x"}}]},
    )
    state = SimpleNamespace(tasks=[SimpleNamespace(interrupts=[intr])])
    with pytest.raises(ResumeValidationError) as ei:
        validate_resume_against_state(
            state,
            [
                {
                    "interruptId": "i1",
                    "decisions": [{"type": "approve"}],
                    "actionHash": "deadbeefdeadbeef",
                }
            ],
        )
    assert ei.value.status_code == 409


def test_validate_resume_requires_action_hash_on_approve():
    """批准时缺少 actionHash → 422。"""
    intr = SimpleNamespace(
        id="i1",
        value={"action_requests": [{"name": "execute", "args": {"command": "pip install x"}}]},
    )
    state = SimpleNamespace(tasks=[SimpleNamespace(interrupts=[intr])])
    with pytest.raises(ResumeValidationError) as ei:
        validate_resume_against_state(
            state,
            [{"interruptId": "i1", "decisions": [{"type": "approve"}]}],
        )
    assert ei.value.status_code == 422
    assert "actionHash" in str(ei.value)


@pytest.mark.asyncio
async def test_run_registry_conflict_and_cancel():
    reset_run_registry_for_tests()
    reg = RunRegistry()
    a = await reg.try_begin("s1", run_id="r1")
    assert a.run_id == "r1"
    with pytest.raises(RunConflictError):
        await reg.try_begin("s1")
    assert await reg.cancel("s1", "r1") is True
    assert reg.get("s1") is not None  # still registered until end
    assert reg.get("s1").cancelled is True
    await reg.end("s1", "r1")
    assert reg.get("s1") is None
    # 取消后可再开
    b = await reg.try_begin("s1", run_id="r2")
    assert b.run_id == "r2"
    await reg.end("s1", "r2")
