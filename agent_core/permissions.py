"""工具级权限矩阵：allow / ask / deny + agent / plan 模式。

默认对齐工作区 Auto（Codex workspace-write + on-request / Claude acceptEdits）：
- write_file / edit_file → allow（物理写入仍限 workspace/tmp|output）
- execute → 按命令分类：auto 跳过 HITL；ask 才弹审批；deny 直接拒绝

ask → 写入 interrupt_on（带 when 谓词），由 HumanInTheLoop 暂停；
      用户批准后 execute 以 hitl_approved 信任级别运行。
deny → 不进 HITL，由 Hooks middleware 硬拒绝。
allow → 直接执行。
"""
from __future__ import annotations

import os
from typing import Any, Literal

from agent_core.execute_policy import classify_for_profile

Permission = Literal["allow", "ask", "deny"]
AgentMode = Literal["agent", "plan"]
Entrypoint = Literal["web", "cli", "channel"]

# 文件系统只读类工具（deepagents FilesystemMiddleware 注入）
_READ_TOOLS = frozenset({
    "read_file",
    "ls",
    "glob",
    "grep",
    "inspect_file",
    "check_research_material",
})

# 写文件类工具
_WRITE_TOOLS = frozenset({
    "write_file",
    "edit_file",
    "replace_file",
})

# 规划 / 委托类（plan 模式也允许）
_PLANNING_TOOLS = frozenset({
    "write_todos",
    "task",
})

# 内容级提问（工具内部 interrupt；不进 interrupt_on）
_ASK_USER_TOOLS = frozenset({
    "ask_user_question",
})


def _env_permission(name: str, default: Permission) -> Permission:
    raw = os.getenv(name, "").strip().lower()
    if raw in ("allow", "ask", "deny"):
        return raw  # type: ignore[return-value]
    return default


def default_mode() -> AgentMode:
    raw = os.getenv("AGENT_MODE", "agent").strip().lower()
    return "plan" if raw == "plan" else "agent"


def is_safe_readonly_shell(command: str | None) -> bool:
    """兼容旧 API：命令可自动执行（workspace_auto 下 effect=auto）。"""
    return classify_for_profile(command).effect == "auto"


def resolve_permission(
    tool_name: str,
    *,
    mode: AgentMode = "agent",
    entrypoint: Entrypoint = "web",
    hitl_enabled: bool = True,
    always_approve: bool = False,
    tool_args: dict | None = None,
) -> Permission:
    """解析单个工具的权限。

    优先级：
    1. plan 模式：写/execute → deny；只读/规划 → allow
    2. channel：写/execute → deny（无 UI 无法 ask）
    3. always_approve：ask → allow
    4. env 覆盖 PERMISSION_EXECUTE / PERMISSION_WRITE
    5. 默认矩阵 + execute 命令分类（workspace_auto）
    """
    name = (tool_name or "").strip()

    if mode == "plan":
        if name in _READ_TOOLS or name in _PLANNING_TOOLS or name in _ASK_USER_TOOLS:
            return "allow"
        if name in _WRITE_TOOLS or name == "execute":
            return "deny"
        if name in ("get_current_time", "render_html", "view_image", "web_search", "web_fetch",
                    "kb_search", "kb_add_document"):
            return "allow"
        return "deny"

    if entrypoint == "channel":
        channel_deny_execute = os.getenv("CHANNEL_DENY_EXECUTE", "true").lower() in (
            "1", "true", "yes",
        )
        if name in _WRITE_TOOLS:
            return "deny"
        if name == "execute" and channel_deny_execute:
            return "deny"
        return "allow"

    # --- agent 模式（web / cli）---
    if name in _READ_TOOLS or name in _PLANNING_TOOLS or name in _ASK_USER_TOOLS:
        return "allow"
    if name in ("get_current_time", "render_html", "view_image"):
        return "allow"
    if name in ("web_search", "web_fetch", "kb_search", "kb_add_document"):
        return "allow"

    if name == "execute":
        default_exec: Permission = "ask" if hitl_enabled else "allow"
        perm = _env_permission("PERMISSION_EXECUTE", default_exec)
        # 工具级 env=allow/deny 优先；否则按命令分类细化
        if perm == "ask" and tool_args is not None:
            cmd = None
            if isinstance(tool_args, dict):
                cmd = tool_args.get("command")
            classification = classify_for_profile(cmd if isinstance(cmd, str) else None)
            if classification.effect == "auto":
                perm = "allow"
            elif classification.effect == "deny":
                # deny 由 sandbox/hooks 处理；避免无意义审批
                perm = "deny"
        elif perm == "ask" and tool_args is None:
            # 无 args 时保持工具级 ask（interrupt_on 用 when 再细分）
            pass
    elif name in _WRITE_TOOLS:
        default_write: Permission = "allow"
        perm = _env_permission("PERMISSION_WRITE", default_write)
    else:
        return "deny"

    if always_approve and perm == "ask":
        return "allow"
    return perm


def _execute_needs_interrupt(request: Any) -> bool:
    """HumanInTheLoopMiddleware when 谓词：仅 ask 类命令才 interrupt。"""
    tool_call = getattr(request, "tool_call", None) or {}
    if not isinstance(tool_call, dict):
        return True
    args = tool_call.get("args") or {}
    cmd = args.get("command") if isinstance(args, dict) else None
    if _env_permission("PERMISSION_EXECUTE", "ask") == "allow":
        return False
    if _env_permission("PERMISSION_EXECUTE", "ask") == "deny":
        return False
    classification = classify_for_profile(cmd if isinstance(cmd, str) else None)
    return classification.effect == "ask"


def build_interrupt_on(
    *,
    mode: AgentMode = "agent",
    entrypoint: Entrypoint = "web",
    hitl_enabled: bool = True,
    always_approve: bool = False,
) -> dict[str, bool | dict] | None:
    """根据矩阵生成 create_deep_agent(interrupt_on=...) 参数。

    execute 使用 InterruptOnConfig + when：workspace_auto 下仅高风险命令弹窗。
    """
    if not hitl_enabled or always_approve:
        return None
    if mode == "plan" or entrypoint == "channel":
        return None

    known = sorted(_WRITE_TOOLS | {"execute"})
    interrupt: dict[str, bool | dict] = {}
    for tool in known:
        if resolve_permission(
            tool,
            mode=mode,
            entrypoint=entrypoint,
            hitl_enabled=hitl_enabled,
            always_approve=always_approve,
        ) == "ask":
            if tool == "execute":
                interrupt[tool] = {
                    "allowed_decisions": ["approve", "reject"],
                    "when": _execute_needs_interrupt,
                    "description": (
                        "Shell 命令需要确认（任意代码执行 / 联网 / 安装 / 未知命令）。"
                        "批准仅针对本次调用；硬拒绝策略（命令替换、灾难性命令）仍不可绕过。"
                    ),
                }
            else:
                interrupt[tool] = True

    return interrupt or None


def deny_message(tool_name: str, *, mode: AgentMode, entrypoint: Entrypoint) -> str:
    """Hooks 硬拒绝时返回给模型的说明文案。"""
    if mode == "plan":
        return (
            f"[E_PERMISSION_DENIED] 当前为 Plan 模式，禁止调用 `{tool_name}`。"
            "请只做只读探查与 write_todos 规划；需要执行写入或 shell 时，请用户切换到 Agent 模式。"
        )
    if entrypoint == "channel":
        return (
            f"[E_PERMISSION_DENIED] 渠道入口禁止调用 `{tool_name}`"
            "（无交互确认界面）。请改用只读工具，或引导用户在 Web/CLI 完成该操作。"
        )
    return f"[E_PERMISSION_DENIED] 策略拒绝调用工具 `{tool_name}`。"


def execute_deny_message(command: str | None) -> str:
    """execute 被策略 deny（硬拒绝）时的文案。"""
    c = classify_for_profile(command)
    note = c.risk_note or c.reason
    return (
        f"[E_PERMISSION_DENIED] 命令被硬策略拒绝，无法批准绕过。"
        f" 原因：{note}"
    )
