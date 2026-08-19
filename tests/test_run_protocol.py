"""RunRegistry / resume 校验 / 协议层单测。"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from langgraph.types import Command

from agent_core.run_registry import RunConflictError, RunRegistry, reset_run_registry_for_tests
from tools.ask_user_question import (
    ResumeValidationError,
    action_hash,
    collect_interrupt_groups,
    validate_resume_against_state,
)


def test_resume_request_preserves_mode():
    """前端传入的 mode 必须保留；否则 /chat/resume 读取 req.mode 会直接 500。"""
    from entrypoints.web import ResumeRequest

    req = ResumeRequest.model_validate(
        {"sessionId": "s1", "mode": "agent", "decisions": []}
    )
    assert req.mode == "agent"
    assert req.model_dump()["mode"] == "agent"


def test_resume_route_accepts_mode_and_starts_resume(monkeypatch):
    """接口级回归：ask_user_question 回答应进入 Command(resume=...) 流。"""
    import entrypoints.web as web
    from agent_core.run_registry import reset_run_registry_for_tests

    interrupt = SimpleNamespace(
        id="ask-1",
        value={
            "kind": "ask_user_question",
            "title": "确认",
            "questions": [
                {
                    "id": "plan_confirm",
                    "prompt": "是否批准？",
                    "options": ["批准执行", "不批准"],
                }
            ],
        },
    )
    state = SimpleNamespace(tasks=[SimpleNamespace(interrupts=[interrupt])])

    class FakeAgent:
        async def aget_state(self, _config):
            return state

    async def fake_get_agent(mode=None):
        assert mode == "agent"
        return FakeAgent()

    captured = {}

    async def fake_run_event_stream(**kwargs):
        captured.update(kwargs)
        yield {"event": "message", "data": '{"type":"done","messageId":"m1"}'}

    reset_run_registry_for_tests()
    monkeypatch.setattr(web, "get_agent", fake_get_agent)
    monkeypatch.setattr(web, "_run_event_stream", fake_run_event_stream)

    response = TestClient(web.app).post(
        "/chat/resume",
        json={
            "sessionId": "s1",
            "mode": "agent",
            "decisions": [
                {
                    "interruptId": "ask-1",
                    "kind": "ask_user_question",
                    "answers": [
                        {
                            "questionId": "plan_confirm",
                            "selected": ["批准执行"],
                            "text": "",
                        }
                    ],
                }
            ],
        },
    )

    assert response.status_code == 200
    assert isinstance(captured["input_payload"], Command)
    assert captured["session_id"] == "s1"


def test_chat_state_ignores_next_without_real_interrupt(monkeypatch):
    """取消后的 next 节点不应被误报成待审批，否则前端会恢复幽灵弹窗。"""
    import entrypoints.web as web

    state = SimpleNamespace(
        next=("agent",),
        tasks=[],
        values={"messages": [], "todos": []},
        config={"configurable": {"checkpoint_id": "cp-1"}},
    )

    class FakeAgent:
        async def aget_state(self, _config):
            return state

    async def fake_get_agent(mode=None):
        return FakeAgent()

    reset_run_registry_for_tests()
    monkeypatch.setattr(web, "get_agent", fake_get_agent)

    response = TestClient(web.app).get("/chat/state", params={"sessionId": "s1"})

    assert response.status_code == 200
    assert response.json()["hasInterrupt"] is False
    assert response.json()["interruptGroups"] == []


def _obsolete_research_confirmation_persists_approval(tmp_path, monkeypatch):
    """明确回答批准时，后端必须先落盘 approved，不能依赖模型再调工具。"""
    import entrypoints.web as web

    monkeypatch.setattr("agent_core.config.RESEARCH_STATE_DIR", tmp_path)
    plan = web.ResearchControlPlane().create_run(
        task="x", mode="deep", run_id="research-12345678-1234-1234-1234-123456789abc",
        must_answer=["capability", "risk", "cost"],
    )
    web.ResearchStore(plan.run_id).event(
        "research_candidates_added", {"phase": "orientation", "count": 3}
    )
    plan = web.ResearchControlPlane().revise(
        plan.run_id, units=[{
            **item.model_dump(mode="json"),
            "acceptance_criteria": [item.question, f"{item.question} boundary"],
        } for item in plan.units]
    )
    interrupt = SimpleNamespace(
        id="ask-research",
        value={
            "kind": "ask_user_question",
            "title": "研究计划确认",
            "questions": [
                {
                    "id": "plan_confirm",
                    "prompt": f"run_id: {plan.run_id}，是否批准执行？",
                    "options": ["批准执行", "不批准"],
                }
            ],
        },
    )
    state = SimpleNamespace(tasks=[SimpleNamespace(interrupts=[interrupt])])
    items = [
        {
            "interruptId": "ask-research",
            "kind": "ask_user_question",
            "answers": [
                {
                    "questionId": "plan_confirm",
                    "selected": ["批准执行"],
                    "text": "",
                }
            ],
        }
    ]

    assert web._approve_research_plans_from_resume(state, items) == [plan.run_id]
    persisted = web.ResearchStore(plan.run_id).read_json("plan.json")
    assert persisted["status"] == "approved"


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


@pytest.mark.asyncio
async def test_sse_disconnect_marks_active_run_cancelled(monkeypatch):
    """断开的 SSE 不得留下会永久阻塞后续 resume 的 active run。"""
    import entrypoints.web as web
    import agent_core.run_registry as registry_module

    reg = RunRegistry()
    monkeypatch.setattr(registry_module, "_registry", reg)
    await reg.try_begin("s1", run_id="r1")

    handler = web._client_disconnect_handler("s1")
    await handler({"type": "http.disconnect"})

    assert reg.get("s1") is not None
    assert reg.get("s1").cancelled is True
    replacement = await reg.try_begin("s1", run_id="r2")
    assert replacement.run_id == "r2"
