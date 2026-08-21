"""执行命令策略：默认放行，仅拦截可识别的删除命令。

这里是权限层、HITL 谓词和沙箱包装器共用的命令分类入口。
删除检测是命令形态级的：它检查命令头、明确的删除子命令以及 shell
包装器中的嵌套命令，不解析任意脚本或解释器内部的文件系统 API。
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Literal

from sandbox.constants import _DELETE_COMMAND_HEADS, _DELETE_SUBCOMMANDS
from sandbox.path_rewriter import (
    _extract_command_head,
    _split_into_segments,
    _split_segment_tokens,
    _tokens_after_env_assignments,
)

ExecuteEffect = Literal["auto", "ask", "deny"]
ExecuteProfile = Literal["workspace_auto", "manual"]

_SHELL_WRAPPER_OPTIONS: dict[str, frozenset[str]] = {
    "sh": frozenset({"-c", "-s"}),
    "bash": frozenset({"-c", "-s"}),
    "zsh": frozenset({"-c", "-s"}),
    "cmd": frozenset({"/c", "/k"}),
    "powershell": frozenset({"-command", "-c", "-encodedcommand", "-enc"}),
    "pwsh": frozenset({"-command", "-c", "-encodedcommand", "-enc"}),
}
_COMMAND_WRAPPERS = frozenset({"sudo", "doas", "runas", "xargs"})


@dataclass(frozen=True)
class ExecuteClassification:
    effect: ExecuteEffect
    reason: str
    risk_note: str = ""
    command_head: str | None = None

    @property
    def needs_hitl(self) -> bool:
        return self.effect == "ask"


def execute_profile() -> ExecuteProfile:
    """返回默认执行档案；manual 作为显式的兼容性收紧开关保留。"""
    raw = os.getenv("EXECUTE_PROFILE", "workspace_auto").strip().lower()
    if raw in ("manual", "ask_all", "legacy"):
        return "manual"
    return "workspace_auto"


def _normalize_head(raw: str | None) -> str | None:
    if not raw:
        return None
    head = raw.strip().lower().replace("\\", "/").rsplit("/", 1)[-1]
    for suffix in (".exe", ".cmd", ".bat", ".ps1", ".com"):
        if head.endswith(suffix):
            head = head[: -len(suffix)]
            break
    if re.fullmatch(r"python\d+(\.\d+)*", head):
        return "python3" if head.startswith("python3") else "python"
    return head or None


def _contains_delete_head(command: str) -> bool:
    """在一个 shell 命令文本中检查直接或嵌套的删除操作。"""
    delete_heads = "|".join(re.escape(head) for head in sorted(_DELETE_COMMAND_HEADS, key=len, reverse=True))
    nested_delete = re.compile(
        rf"(?:\$\(\s*|`\s*|[;&|]\s*)(?:{delete_heads})(?=\s|$)",
        re.IGNORECASE,
    )
    if nested_delete.search(command):
        return True

    segments = _split_into_segments(command)
    if not segments:
        return False

    for segment in segments:
        raw_tokens = _split_segment_tokens(segment)
        tokens = _tokens_after_env_assignments(list(raw_tokens))
        if not tokens:
            continue

        head = _normalize_head(_extract_command_head(segment))
        if head in _DELETE_COMMAND_HEADS:
            return True

        delete_subcommands = _DELETE_SUBCOMMANDS.get(head or "", frozenset())
        if any(token.lower() in delete_subcommands for token in tokens[1:]):
            return True

        if head == "find":
            for marker in ("-exec", "-execdir"):
                if marker in (token.lower() for token in tokens[1:]):
                    marker_index = next(
                        index for index, token in enumerate(tokens[1:], start=1)
                        if token.lower() == marker
                    )
                    if _contains_delete_head(" ".join(tokens[marker_index + 1 :])):
                        return True

        if head in _COMMAND_WRAPPERS and _contains_delete_head(" ".join(tokens[1:])):
            return True

        if head in _SHELL_WRAPPER_OPTIONS:
            options = _SHELL_WRAPPER_OPTIONS[head]
            for index, token in enumerate(tokens[1:], start=1):
                if (
                    token.lower() in options
                    and index + 1 < len(tokens)
                    and _contains_delete_head(" ".join(tokens[index + 1 :]))
                ):
                    return True

        # 命令替换/反引号中的删除命令属于实际执行的嵌套命令；
        # 普通 echo "rm x" 不会命中这些边界。
        for nested in re.findall(r"\$\(\s*([^)]*)\)|`([^`]*)`", segment):
            nested_command = next((part for part in nested if part), "")
            if nested_command and _contains_delete_head(nested_command):
                return True

    return False


def classify_execute_command(command: str | None) -> ExecuteClassification:
    """分类整条命令：可识别删除命令 deny，其余有效命令 auto。"""
    if not command or not str(command).strip():
        return ExecuteClassification(
            effect="ask",
            reason="empty",
            risk_note="空命令，无法执行。",
        )

    cmd = str(command).strip()
    if _contains_delete_head(cmd):
        return ExecuteClassification(
            effect="deny",
            reason="delete_command",
            risk_note="命令包含可识别的删除操作，已被安全策略拦截。",
        )

    segments = _split_into_segments(cmd)
    head = _normalize_head(_extract_command_head(segments[0])) if segments else None
    return ExecuteClassification(
        effect="auto",
        reason="allowed_command",
        risk_note="非删除命令按当前执行策略直接放行。",
        command_head=head,
    )


def classify_for_profile(
    command: str | None,
    *,
    profile: ExecuteProfile | None = None,
) -> ExecuteClassification:
    """应用 EXECUTE_PROFILE；manual 只把非删除命令提升为 ask。"""
    base = classify_execute_command(command)
    prof = profile or execute_profile()
    if prof == "manual" and base.effect == "auto":
        return ExecuteClassification(
            effect="ask",
            reason="manual_profile",
            risk_note="当前为 manual 配置：每条非删除 execute 均需确认。",
            command_head=base.command_head,
        )
    return base


def hitl_reason_for_ui(classification: ExecuteClassification) -> str:
    """给前端审批卡片的短说明。"""
    if classification.risk_note:
        return classification.risk_note
    return f"需要确认：{classification.reason}"
