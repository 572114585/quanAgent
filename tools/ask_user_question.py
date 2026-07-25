"""向用户提问并挂起图执行（对齐 grok-build ask_user_question）。

通过 langgraph.types.interrupt 暂停；Web/CLI resume 后答案作为 interrupt() 返回值。
不放入 interrupt_on：工具执行后自行 interrupt，避免双重拦截。
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Any, Iterator

from langchain_core.tools import tool
from langgraph.types import interrupt

logger = logging.getLogger(__name__)

ASK_USER_KIND = "ask_user_question"


class ResumeValidationError(ValueError):
    """resume 载荷与当前 pending interrupt 不匹配。"""

    def __init__(self, message: str, *, status_code: int = 422):
        super().__init__(message)
        self.status_code = status_code


def action_hash(tool_name: str, tool_args: Any) -> str:
    """稳定摘要：工具名 + 参数，供审批与执行参数一致性校验。"""
    try:
        args_json = json.dumps(tool_args or {}, sort_keys=True, ensure_ascii=False, default=str)
    except TypeError:
        args_json = str(tool_args)
    raw = f"{tool_name}|{args_json}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

# 由 HooksMiddleware 按 entrypoint 设置；channel 等无 UI 入口跳过 interrupt
_ask_user_noninteractive: ContextVar[bool] = ContextVar(
    "ask_user_noninteractive", default=False
)


def set_ask_user_noninteractive(flag: bool) -> Token:
    return _ask_user_noninteractive.set(flag)


def reset_ask_user_noninteractive(token: Token) -> None:
    _ask_user_noninteractive.reset(token)


@contextmanager
def ask_user_noninteractive(flag: bool) -> Iterator[None]:
    token = set_ask_user_noninteractive(flag)
    try:
        yield
    finally:
        reset_ask_user_noninteractive(token)


def normalize_questions(raw: Any) -> list[dict[str, Any]]:
    """校验并规范化 questions 列表。"""
    if not isinstance(raw, list) or not raw:
        raise ValueError("questions 必须是非空列表")
    out: list[dict[str, Any]] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"questions[{i}] 必须是对象")
        qid = str(item.get("id") or f"q{i + 1}").strip()
        prompt = str(item.get("prompt") or "").strip()
        if not prompt:
            raise ValueError(f"questions[{i}].prompt 不能为空")
        options = item.get("options")
        if options is None:
            opts: list[str] | None = None
        elif isinstance(options, list):
            opts = [str(o) for o in options if str(o).strip()]
            if not opts:
                opts = None
        else:
            raise ValueError(f"questions[{i}].options 必须是字符串列表或省略")
        allow_multiple = bool(item.get("allowMultiple") or item.get("allow_multiple") or False)
        allow_free = item.get("allowFreeText")
        if allow_free is None:
            allow_free = item.get("allow_free_text")
        if allow_free is None:
            allow_free = True
        out.append(
            {
                "id": qid,
                "prompt": prompt,
                "options": opts,
                "allowMultiple": allow_multiple,
                "allowFreeText": bool(allow_free),
            }
        )
    return out


def build_interrupt_payload(*, title: str, questions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "kind": ASK_USER_KIND,
        "title": (title or "需要你的确认").strip() or "需要你的确认",
        "questions": questions,
    }


def format_answers(answers_payload: Any, *, questions: list[dict[str, Any]]) -> str:
    """把 resume 载荷格式化为模型可读摘要。"""
    if not isinstance(answers_payload, dict):
        return f"用户回复（非结构化）：{answers_payload!r}"

    answers = answers_payload.get("answers")
    if not isinstance(answers, list):
        # 兼容直接传单题答案
        if "selected" in answers_payload or "text" in answers_payload:
            answers = [answers_payload]
        else:
            return f"用户回复：{answers_payload!r}"

    by_id = {str(a.get("questionId") or a.get("question_id") or ""): a for a in answers if isinstance(a, dict)}
    lines = ["用户已回答："]
    for q in questions:
        qid = q["id"]
        a = by_id.get(qid, {})
        selected = a.get("selected") or []
        if isinstance(selected, str):
            selected = [selected]
        text = str(a.get("text") or "").strip()
        parts: list[str] = []
        if selected:
            parts.append("选项=" + "、".join(str(s) for s in selected))
        if text:
            parts.append("补充=" + text)
        if not parts:
            parts.append("（未作答）")
        lines.append(f"- [{qid}] {q['prompt']}: {'; '.join(parts)}")
    return "\n".join(lines)


def _normalize_tool_calls(action_requests: Any) -> list[dict[str, Any]]:
    """为 tool_approval 的 action_requests 注入 actionHash 与风险说明。"""
    out: list[dict[str, Any]] = []
    if not isinstance(action_requests, list):
        return out
    for req in action_requests:
        if not isinstance(req, dict):
            continue
        name = str(req.get("name") or req.get("action") or "")
        args = req.get("args") if "args" in req else req.get("arguments")
        item = dict(req)
        item["actionHash"] = action_hash(name, args)
        # execute：附加分类风险说明，供前端审批卡片展示
        if name == "execute" and isinstance(args, dict):
            cmd = args.get("command")
            if isinstance(cmd, str):
                try:
                    from agent_core.execute_policy import (
                        classify_for_profile,
                        hitl_reason_for_ui,
                    )

                    cls = classify_for_profile(cmd)
                    item["riskNote"] = hitl_reason_for_ui(cls)
                    item["riskReason"] = cls.reason
                except Exception:  # noqa: BLE001
                    item["riskNote"] = "高风险 shell 命令，批准仅针对本次调用。"
        if not item.get("description") and item.get("riskNote"):
            item["description"] = item["riskNote"]
        out.append(item)
    return out


def collect_interrupt_groups(state: Any) -> list[dict[str, Any]]:
    """从 LangGraph state 收集 interrupt 分组（tool_approval + ask_user_question）。"""
    groups: list[dict[str, Any]] = []
    tasks = getattr(state, "tasks", None) or ()
    for task in tasks:
        for intr in getattr(task, "interrupts", None) or ():
            value = getattr(intr, "value", None)
            if not isinstance(value, dict):
                continue
            iid = getattr(intr, "id", None) or ""
            action_requests = value.get("action_requests")
            if action_requests:
                tool_calls = _normalize_tool_calls(action_requests)
                groups.append(
                    {
                        "interruptId": iid,
                        "kind": "tool_approval",
                        "toolCalls": tool_calls,
                        "actionHash": tool_calls[0]["actionHash"] if tool_calls else "",
                    }
                )
                continue
            if value.get("kind") == ASK_USER_KIND:
                groups.append(
                    {
                        "interruptId": iid,
                        "kind": ASK_USER_KIND,
                        "title": value.get("title") or "需要你的确认",
                        "questions": value.get("questions") or [],
                    }
                )
    return groups


def build_resume_map(items: list[dict[str, Any]]) -> dict[str, Any]:
    """把前端/CLI 提交的 decisions 列表转成 Command(resume=...) 映射。

    每项至少含 interruptId；tool_approval 用 decisions，ask_user_question 用 answers。
    生产路径请优先用 validate_resume_against_state。
    """
    resume_map: dict[str, Any] = {}
    for item in items:
        iid = str(item.get("interruptId") or item.get("interrupt_id") or "")
        if not iid:
            continue
        kind = item.get("kind") or ""
        if kind == ASK_USER_KIND or "answers" in item:
            resume_map[iid] = {"answers": item.get("answers") or []}
        else:
            resume_map[iid] = {"decisions": item.get("decisions") or []}
    return resume_map


def validate_resume_against_state(
    state: Any,
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    """校验 decisions 与当前 pending interrupt 完全匹配后返回 resume_map。

    拒绝：空列表、缺失/多余 interruptId、空 decisions/answers、
    tool_approval 批准时 actionHash 与 pending 不一致。
    """
    pending = collect_interrupt_groups(state)
    if not pending:
        raise ResumeValidationError(
            "当前会话没有待处理的 interrupt",
            status_code=409,
        )
    if not items:
        raise ResumeValidationError("decisions 不能为空", status_code=422)

    pending_by_id = {str(g["interruptId"]): g for g in pending if g.get("interruptId")}
    submitted_ids: set[str] = set()
    for item in items:
        iid = str(item.get("interruptId") or item.get("interrupt_id") or "").strip()
        if not iid:
            raise ResumeValidationError("每项 decisions 必须包含 interruptId", status_code=422)
        if iid in submitted_ids:
            raise ResumeValidationError(f"重复的 interruptId: {iid}", status_code=422)
        submitted_ids.add(iid)
        if iid not in pending_by_id:
            raise ResumeValidationError(
                f"未知或已过期的 interruptId: {iid}",
                status_code=409,
            )
        group = pending_by_id[iid]
        kind = item.get("kind") or group.get("kind") or ""
        if kind == ASK_USER_KIND or group.get("kind") == ASK_USER_KIND:
            answers = item.get("answers")
            if not isinstance(answers, list) or not answers:
                raise ResumeValidationError(
                    f"ask_user_question interrupt {iid} 需要非空 answers",
                    status_code=422,
                )
        else:
            decisions = item.get("decisions")
            if not isinstance(decisions, list) or not decisions:
                raise ResumeValidationError(
                    f"tool_approval interrupt {iid} 需要非空 decisions",
                    status_code=422,
                )
            # 任一 approve 时必须校验 actionHash（防参数篡改）
            client_hash = str(item.get("actionHash") or "").strip()
            expected = str(group.get("actionHash") or "").strip()
            has_approve = any(
                isinstance(d, dict) and d.get("type") == "approve" for d in decisions
            )
            if has_approve:
                if not client_hash:
                    raise ResumeValidationError(
                        f"interrupt {iid} 批准时必须提交 actionHash",
                        status_code=422,
                    )
                if expected and client_hash != expected:
                    raise ResumeValidationError(
                        f"interrupt {iid} 的 actionHash 与待批准动作不一致",
                        status_code=409,
                    )
            for d in decisions:
                if not isinstance(d, dict):
                    continue
                if d.get("type") == "approve" and client_hash and expected and client_hash != expected:
                    raise ResumeValidationError(
                        f"interrupt {iid} 批准参数已变更，请重新审批",
                        status_code=409,
                    )

    missing = set(pending_by_id) - submitted_ids
    if missing:
        raise ResumeValidationError(
            f"缺少对 pending interrupt 的决定: {sorted(missing)}",
            status_code=422,
        )

    return build_resume_map(items)


def _channel_or_headless() -> bool:
    """渠道等无交互 UI 的入口：不 interrupt，避免挂死。"""
    if _ask_user_noninteractive.get():
        return True
    return os.getenv("ASK_USER_QUESTION_NONINTERACTIVE", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


@tool
def ask_user_question(
    title: str,
    questions: list[dict],
) -> str:
    """向用户提出一个或多个确认/澄清问题，并等待真实回复后再继续。

    用于 Skill 声明的 Checkpoint（大纲确认、终稿确认、需求澄清等）。
    **必须**调用本工具等待用户；禁止用纯文本「请确认」后自行假设已通过。

    Args:
        title: 问卷标题，如「大纲确认」。
        questions: 问题列表。每项字段：
            - id (str): 稳定问题 id
            - prompt (str): 题干
            - options (list[str], 可选): 预设选项
            - allowMultiple (bool, 可选): 是否可多选，默认 false
            - allowFreeText (bool, 可选): 是否允许自由文本，默认 true
    """
    normalized = normalize_questions(questions)
    payload = build_interrupt_payload(title=title, questions=normalized)

    if _channel_or_headless():
        logger.info("ask_user_question blocked (non-interactive): title=%s", payload["title"])
        return (
            "[E_ASK_USER_UNAVAILABLE] 当前入口无法收集用户确认，已停止该检查点。"
            "请引导用户到 Web/CLI 完成确认，禁止假设已通过。"
        )

    raw = interrupt(payload)
    return format_answers(raw, questions=normalized)
