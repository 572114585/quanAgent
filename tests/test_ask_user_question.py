"""ask_user_question：规范化、答案格式化、interrupt 分组与 resume map。"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from agent_core.permissions import build_interrupt_on, resolve_permission
from tools.ask_user_question import (
    ASK_USER_KIND,
    build_interrupt_payload,
    build_resume_map,
    collect_interrupt_groups,
    format_answers,
    normalize_questions,
)


def test_normalize_questions_ok():
    qs = normalize_questions(
        [
            {"id": "a", "prompt": "结构OK？", "options": ["是", "否"], "allowMultiple": False},
            {"prompt": "补充？"},  # id 自动生成
        ]
    )
    assert qs[0]["id"] == "a"
    assert qs[0]["options"] == ["是", "否"]
    assert qs[1]["id"] == "q2"
    assert qs[1]["allowFreeText"] is True


def test_normalize_questions_rejects_empty():
    with pytest.raises(ValueError):
        normalize_questions([])


def test_format_answers():
    qs = normalize_questions(
        [{"id": "structure", "prompt": "结构？", "options": ["继续", "调整"]}]
    )
    text = format_answers(
        {"answers": [{"questionId": "structure", "selected": ["继续"], "text": "ok"}]},
        questions=qs,
    )
    assert "用户已回答" in text
    assert "继续" in text
    assert "ok" in text


def test_build_interrupt_payload_kind():
    qs = normalize_questions([{"id": "q1", "prompt": "确认？"}])
    payload = build_interrupt_payload(title="大纲确认", questions=qs)
    assert payload["kind"] == ASK_USER_KIND
    assert payload["title"] == "大纲确认"
    assert len(payload["questions"]) == 1


def test_collect_interrupt_groups_mixed():
    state = SimpleNamespace(
        tasks=[
            SimpleNamespace(
                interrupts=[
                    SimpleNamespace(
                        id="i1",
                        value={
                            "action_requests": [{"name": "execute", "args": {"command": "ls"}}]
                        },
                    ),
                    SimpleNamespace(
                        id="i2",
                        value={
                            "kind": ASK_USER_KIND,
                            "title": "大纲确认",
                            "questions": [{"id": "q1", "prompt": "OK?"}],
                        },
                    ),
                ]
            )
        ]
    )
    groups = collect_interrupt_groups(state)
    assert len(groups) == 2
    kinds = {g["kind"] for g in groups}
    assert kinds == {"tool_approval", ASK_USER_KIND}
    ask = next(g for g in groups if g["kind"] == ASK_USER_KIND)
    assert ask["title"] == "大纲确认"
    assert ask["interruptId"] == "i2"


def test_build_resume_map():
    m = build_resume_map(
        [
            {"interruptId": "a", "kind": "tool_approval", "decisions": [{"type": "approve"}]},
            {
                "interruptId": "b",
                "kind": ASK_USER_KIND,
                "answers": [{"questionId": "q1", "selected": ["是"], "text": ""}],
            },
        ]
    )
    assert m["a"] == {"decisions": [{"type": "approve"}]}
    assert m["b"]["answers"][0]["selected"] == ["是"]


def test_ask_user_permission_allow_in_agent_and_plan():
    assert (
        resolve_permission("ask_user_question", mode="agent", entrypoint="web", hitl_enabled=True)
        == "allow"
    )
    assert (
        resolve_permission("ask_user_question", mode="plan", entrypoint="web", hitl_enabled=True)
        == "allow"
    )


def test_ask_user_not_in_interrupt_on():
    interrupt = build_interrupt_on(mode="agent", entrypoint="web", hitl_enabled=True)
    assert interrupt is not None
    assert "ask_user_question" not in interrupt
    assert "execute" in interrupt
    assert isinstance(interrupt["execute"], (bool, dict))


def test_noninteractive_returns_unavailable():
    from tools.ask_user_question import ask_user_noninteractive, ask_user_question

    with ask_user_noninteractive(True):
        out = ask_user_question.invoke(
            {
                "title": "大纲确认",
                "questions": [{"id": "q1", "prompt": "结构OK？", "options": ["是", "否"]}],
            }
        )
    assert "E_ASK_USER_UNAVAILABLE" in out
    assert "禁止假设" in out
    assert "假设用户确认" not in out
