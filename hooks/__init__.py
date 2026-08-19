"""Hooks：工具调用前后拦截。

before_tool 可返回 allow / deny / ask。
- deny → 直接返回 error ToolMessage，不执行工具
- ask → 本层放行（真正的 ask 由 interrupt_on + HITL 处理；若仍落到此处说明未挂 HITL，按 deny）
- allow → 调用 handler
after_tool 仅审计，不改安全边界。
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import logging
import sys
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal, Sequence

from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.messages import ToolMessage

from agent_core.permissions import (
    AgentMode,
    Entrypoint,
    deny_message,
    execute_deny_message,
    resolve_permission,
)
from agent_core.execute_policy import classify_for_profile
from sandbox.trust import TrustLevel, execute_trust
from tools.ask_user_question import ask_user_noninteractive

logger = logging.getLogger(__name__)

HookAction = Literal["allow", "deny", "ask"]


@dataclass
class HookContext:
    event: str  # before_tool | after_tool
    tool_name: str
    tool_args: dict[str, Any]
    tool_call_id: str
    mode: AgentMode
    entrypoint: Entrypoint
    result: Any = None  # after_tool 时填充


@dataclass
class HookDecision:
    action: HookAction = "allow"
    message: str = ""


HookFn = Callable[[HookContext], HookDecision | dict | None]


@dataclass
class HookRegistration:
    name: str
    before_tool: HookFn | None = None
    after_tool: HookFn | None = None


def _normalize_decision(raw: HookDecision | dict | None) -> HookDecision:
    if raw is None:
        return HookDecision(action="allow")
    if isinstance(raw, HookDecision):
        return raw
    if isinstance(raw, dict):
        action = str(raw.get("action", "allow")).lower()
        if action not in ("allow", "deny", "ask"):
            action = "allow"
        return HookDecision(action=action, message=str(raw.get("message", "") or ""))
    return HookDecision(action="allow")


def _deny_tool_message(tool_call_id: str, name: str, message: str) -> ToolMessage:
    return ToolMessage(
        content=message,
        tool_call_id=tool_call_id,
        name=name,
        status="error",
    )


@dataclass
class HooksRuntime:
    """可复用的 hook 分发器（供 middleware 与测试使用）。"""

    mode: AgentMode = "agent"
    entrypoint: Entrypoint = "web"
    hitl_enabled: bool = True
    always_approve: bool = False
    interrupt_on: frozenset[str] = field(default_factory=frozenset)
    registrations: list[HookRegistration] = field(default_factory=list)

    def run_before(self, ctx: HookContext) -> HookDecision:
        # 1) 内置权限矩阵
        perm = resolve_permission(
            ctx.tool_name,
            mode=self.mode,
            entrypoint=self.entrypoint,
            hitl_enabled=self.hitl_enabled,
            always_approve=self.always_approve,
            tool_args=ctx.tool_args,
        )
        if perm == "deny":
            msg = deny_message(ctx.tool_name, mode=self.mode, entrypoint=self.entrypoint)
            if ctx.tool_name == "execute":
                cmd = (ctx.tool_args or {}).get("command") if isinstance(ctx.tool_args, dict) else None
                if isinstance(cmd, str):
                    msg = execute_deny_message(cmd)
            return HookDecision(action="deny", message=msg)
        if perm == "ask":
            # ask 必须已挂 interrupt_on；否则 fail-closed（防未知工具旁路）
            if (
                not self.hitl_enabled
                or self.always_approve
                or self.mode == "plan"
                or ctx.tool_name not in self.interrupt_on
            ):
                return HookDecision(
                    action="deny",
                    message=deny_message(ctx.tool_name, mode=self.mode, entrypoint=self.entrypoint)
                    + "（ask 未挂 HITL，已拒绝）",
                )

        # 2) 用户 / 脚本 hooks
        for reg in self.registrations:
            if reg.before_tool is None:
                continue
            try:
                decision = _normalize_decision(reg.before_tool(ctx))
            except Exception as e:  # noqa: BLE001
                logger.exception("hook %s before_tool failed", reg.name)
                return HookDecision(
                    action="deny",
                    message=f"[E_HOOK_ERROR] hook `{reg.name}` 执行失败，已拒绝：{e}",
                )
            if decision.action == "deny":
                return decision
            if decision.action == "ask":
                # 脚本要求 ask：无 HITL 或工具未挂 interrupt_on → fail-closed
                if (
                    not self.hitl_enabled
                    or self.always_approve
                    or ctx.tool_name not in self.interrupt_on
                ):
                    return HookDecision(
                        action="deny",
                        message=decision.message
                        or f"[E_PERMISSION_DENIED] hook `{reg.name}` 要求确认，但当前无法 ask。",
                    )
                # 有 HITL 且已挂 interrupt：放行到 HITL（或已批准后进 middleware）
                continue
        return HookDecision(action="allow")

    def run_after(self, ctx: HookContext) -> None:
        for reg in self.registrations:
            if reg.after_tool is None:
                continue
            try:
                reg.after_tool(ctx)
            except Exception:  # noqa: BLE001
                logger.exception("hook %s after_tool failed (ignored)", reg.name)


def builtin_audit_log() -> HookRegistration:
    def before(ctx: HookContext) -> None:
        logger.info(
            "hook.before_tool tool=%s mode=%s entrypoint=%s call_id=%s",
            ctx.tool_name,
            ctx.mode,
            ctx.entrypoint,
            ctx.tool_call_id,
        )
        return None

    def after(ctx: HookContext) -> None:
        logger.info(
            "hook.after_tool tool=%s call_id=%s",
            ctx.tool_name,
            ctx.tool_call_id,
        )
        return None

    return HookRegistration(name="audit_log", before_tool=before, after_tool=after)


def normalize_tool_args(args: dict[str, Any] | None) -> str:
    """稳定序列化工具参数，供盲重试指纹比对。"""
    try:
        payload = json.dumps(args or {}, sort_keys=True, ensure_ascii=False, default=str)
    except TypeError:
        payload = str(args)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


@dataclass
class BlindRetryTracker:
    """按连续相同 tool+args 计数；仅失败 observation 计入盲重试。"""

    max_consecutive: int = 3
    window: deque[str] = field(default_factory=lambda: deque(maxlen=32))
    # fingerprint -> 最近一次是否失败（成功则清零）
    last_failed: dict[str, bool] = field(default_factory=dict)
    fail_streak: dict[str, int] = field(default_factory=dict)

    def fingerprint(self, tool_name: str, tool_args: dict[str, Any] | None, *, thread_id: str = "") -> str:
        base = f"{tool_name}:{normalize_tool_args(tool_args)}"
        return f"{thread_id}:{base}" if thread_id else base

    def consecutive_count(self, fp: str) -> int:
        return int(self.fail_streak.get(fp, 0))

    def record_attempt(self, fp: str) -> int:
        """before_tool：若上一次同指纹失败，则 streak+1；返回即将成为的 streak。"""
        if self.last_failed.get(fp):
            nxt = self.fail_streak.get(fp, 0) + 1
        else:
            nxt = 1
        return nxt

    def mark_result(self, fp: str, *, failed: bool) -> None:
        if failed:
            self.last_failed[fp] = True
            self.fail_streak[fp] = self.fail_streak.get(fp, 0) + 1
            self.window.append(fp)
        else:
            self.last_failed[fp] = False
            self.fail_streak[fp] = 0

    def record(self, fp: str) -> int:
        """兼容旧测试：无 after 时按调用次数计。"""
        self.window.append(fp)
        count = 0
        for item in reversed(self.window):
            if item != fp:
                break
            count += 1
        self.fail_streak[fp] = count
        self.last_failed[fp] = True
        return count


_default_blind_retry_tracker = BlindRetryTracker()


def reset_blind_retry_tracker() -> None:
    """测试用：清空默认盲重试窗口。"""
    _default_blind_retry_tracker.window.clear()
    _default_blind_retry_tracker.last_failed.clear()
    _default_blind_retry_tracker.fail_streak.clear()


def _tool_result_failed(result: Any) -> bool:
    if result is None:
        return False
    status = getattr(result, "status", None)
    if status == "error":
        return True
    content = getattr(result, "content", None)
    if isinstance(content, str) and (
        content.startswith("[E_") or "E_PERMISSION_DENIED" in content or "E_BLIND_RETRY" in content
    ):
        return True
    return False


def builtin_anti_blind_retry(
    *,
    max_consecutive: int = 3,
    tracker: BlindRetryTracker | None = None,
) -> HookRegistration:
    """连续相同 tool+args 在失败后达到阈值时 deny。

    成功调用清零该指纹；仅失败 observation 累加 streak。
    """
    tr = tracker if tracker is not None else BlindRetryTracker(max_consecutive=max_consecutive)
    tr.max_consecutive = max_consecutive
    pending_fp: dict[str, str] = {}

    def before(ctx: HookContext) -> HookDecision | None:
        if ctx.tool_name in ("write_todos",):
            return None

        thread_id = ""
        # HookContext 无 thread_id 字段时用空串；build 时可扩展
        fp = tr.fingerprint(ctx.tool_name, ctx.tool_args, thread_id=thread_id)
        would_be = tr.record_attempt(fp)
        if would_be >= tr.max_consecutive and tr.last_failed.get(fp):
            return HookDecision(
                action="deny",
                message=(
                    f"[E_BLIND_RETRY] 相同工具调用已连续失败 {tr.max_consecutive - 1} 次："
                    f"`{ctx.tool_name}`。请先诊断失败原因，更换参数/策略，"
                    "或向用户说明 blocker；禁止盲重试同一调用。"
                ),
            )
        if ctx.tool_call_id:
            pending_fp[ctx.tool_call_id] = fp
        return None

    def after(ctx: HookContext) -> None:
        fp = pending_fp.pop(ctx.tool_call_id, None) if ctx.tool_call_id else None
        if not fp:
            fp = tr.fingerprint(ctx.tool_name, ctx.tool_args)
        tr.mark_result(fp, failed=_tool_result_failed(ctx.result))

    return HookRegistration(name="anti_blind_retry", before_tool=before, after_tool=after)




def load_script_hooks(hooks_dir: Path) -> list[HookRegistration]:
    """加载 workspace/hooks/*.py（约定 before_tool / after_tool 函数）。"""
    regs: list[HookRegistration] = []
    if not hooks_dir.is_dir():
        return regs
    for path in sorted(hooks_dir.glob("*.py")):
        if path.name.startswith("_"):
            continue
        mod_name = f"deepagent_hooks_{path.stem}"
        try:
            spec = importlib.util.spec_from_file_location(mod_name, path)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = module
            spec.loader.exec_module(module)
            before = getattr(module, "before_tool", None)
            after = getattr(module, "after_tool", None)
            if before is None and after is None:
                logger.warning("hooks script %s has no before_tool/after_tool, skipped", path)
                continue
            regs.append(
                HookRegistration(
                    name=path.stem,
                    before_tool=before if callable(before) else None,
                    after_tool=after if callable(after) else None,
                )
            )
            logger.info("loaded hook script: %s", path)
        except Exception:  # noqa: BLE001
            logger.exception("failed to load hook script %s", path)
    return regs


class HooksMiddleware(AgentMiddleware):
    """LangChain AgentMiddleware：wrap_tool_call / awrap_tool_call。"""

    def __init__(self, runtime: HooksRuntime):
        super().__init__()
        self.runtime = runtime

    def _ctx_from_request(self, request: Any, event: str, result: Any = None) -> HookContext:
        tool_call = getattr(request, "tool_call", None) or {}
        if not isinstance(tool_call, dict):
            tool_call = {}
        return HookContext(
            event=event,
            tool_name=str(tool_call.get("name") or ""),
            tool_args=dict(tool_call.get("args") or {}),
            tool_call_id=str(tool_call.get("id") or ""),
            mode=self.runtime.mode,
            entrypoint=self.runtime.entrypoint,
            result=result,
        )

    def _execute_trust_level(self, tool_name: str, tool_args: dict | None = None) -> TrustLevel:
        """为本次工具调用设定 shell 信任级别。

        - always_approve → hitl_approved
        - execute + 命令分类 ask 且工具在 interrupt_on → 到达 wrap 时视为已 HITL 批准
        - execute + 命令分类 auto → strict 即可（whitelist 按 classification 跳过软层）
        - 不向 task 整体下放信任
        """
        if self.runtime.always_approve:
            return "hitl_approved"
        if tool_name != "execute":
            return "strict"
        if not self.runtime.hitl_enabled:
            return "strict"
        if tool_name not in self.runtime.interrupt_on:
            return "strict"
        cmd = None
        if isinstance(tool_args, dict):
            raw = tool_args.get("command")
            cmd = raw if isinstance(raw, str) else None
        classification = classify_for_profile(cmd)
        # ask 类到达 wrap_tool_call ⇒ 用户已在 interrupt 中批准
        if classification.effect == "ask":
            return "hitl_approved"
        return "strict"

    def wrap_tool_call(self, request: Any, handler: Callable) -> Any:
        ctx = self._ctx_from_request(request, "before_tool")
        decision = self.runtime.run_before(ctx)
        if decision.action == "deny":
            msg = decision.message or deny_message(
                ctx.tool_name, mode=ctx.mode, entrypoint=ctx.entrypoint
            )
            return _deny_tool_message(ctx.tool_call_id, ctx.tool_name, msg)
        trust = self._execute_trust_level(ctx.tool_name, ctx.tool_args)
        with execute_trust(trust):
            with ask_user_noninteractive(self.runtime.entrypoint == "channel"):
                result = handler(request)
        self.runtime.run_after(self._ctx_from_request(request, "after_tool", result=result))
        return result

    async def awrap_tool_call(self, request: Any, handler: Callable) -> Any:
        ctx = self._ctx_from_request(request, "before_tool")
        decision = self.runtime.run_before(ctx)
        if decision.action == "deny":
            msg = decision.message or deny_message(
                ctx.tool_name, mode=ctx.mode, entrypoint=ctx.entrypoint
            )
            return _deny_tool_message(ctx.tool_call_id, ctx.tool_name, msg)
        trust = self._execute_trust_level(ctx.tool_name, ctx.tool_args)
        with execute_trust(trust):
            with ask_user_noninteractive(self.runtime.entrypoint == "channel"):
                result = await handler(request)
        self.runtime.run_after(self._ctx_from_request(request, "after_tool", result=result))
        return result


def build_hooks_middleware(
    *,
    mode: AgentMode,
    entrypoint: Entrypoint,
    hitl_enabled: bool,
    always_approve: bool = False,
    interrupt_on: dict[str, bool | dict] | None = None,
    hooks_dir: Path | None = None,
    extra: Sequence[HookRegistration] = (),
) -> HooksMiddleware:
    regs: list[HookRegistration] = [
        builtin_audit_log(),
        builtin_anti_blind_retry(),
    ]
    if hooks_dir is not None:
        regs.extend(load_script_hooks(hooks_dir))
    regs.extend(extra)
    registered = frozenset(
        name
        for name, enabled in (interrupt_on or {}).items()
        if enabled  # True 或非空 InterruptOnConfig dict
    )
    runtime = HooksRuntime(
        mode=mode,
        entrypoint=entrypoint,
        hitl_enabled=hitl_enabled,
        always_approve=always_approve,
        interrupt_on=registered,
        registrations=regs,
    )
    return HooksMiddleware(runtime)
