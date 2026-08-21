"""工作区 Auto 命令分类：auto / ask / deny。

唯一真相源：HITL `when`、Hooks trust、sandbox 软白名单共用此分类。
- auto：可信工作区内常规本地命令，自动执行（绕过 HITL 与软白名单）
- ask：任意解释器内联、安装、联网、未知命令 —— 需用户批准一次
- deny：命令替换、灾难性操作 —— 永不放行，也不弹审批

非 OS 级沙盒：auto 仅适用于已配置的可信 WORKSPACE_ROOT。
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Literal

from sandbox.constants import (
    _COMMAND_SUBSTITUTION_PATTERN,
    _HARD_DENY_PATTERNS,
)
from sandbox.path_rewriter import (
    _extract_command_head,
    _split_into_segments,
    _split_segment_tokens,
    _tokens_after_env_assignments,
)

ExecuteEffect = Literal["auto", "ask", "deny"]
ExecuteProfile = Literal["workspace_auto", "manual"]

# 只读探查（含 Windows）
_AUTO_READONLY_HEADS = frozenset({
    "ls", "dir", "pwd", "echo", "cat", "type", "head", "tail", "wc",
    "sort", "uniq", "tr", "cut", "date", "whoami", "hostname", "uptime", "ps",
    "which", "where", "where.exe", "env", "printenv", "uname", "find", "test",
    "grep", "findstr", "rg", "tree",
})

# 目录切换（越界由 sandbox 硬拒绝）
_AUTO_CD_HEADS = frozenset({"cd", "pushd", "popd", "chdir"})

# 只读 git
_SAFE_GIT_SUBCMDS = frozenset({
    "status", "branch", "log", "diff", "show", "ls-files", "rev-parse",
    "describe", "remote", "tag", "stash", "shortlog", "blame",
})

# 已知构建 / 测试 / 格式化（无 install / publish）
_AUTO_BUILD_HEADS = frozenset({
    "pytest", "python", "python3", "py",
    "npm", "npx", "node", "yarn", "pnpm",
    "make", "cmake", "ninja",
    "cargo", "go", "javac", "java",
    "tsc", "vue-tsc", "eslint", "prettier", "ruff", "mypy", "black", "isort",
    "jq", "zip", "unzip", "tar",
    "bash", "sh",
})

# 明确需审批：安装 / 发包 / 任意解释器内联
_ASK_INSTALL_HEADS = frozenset({
    "pip", "pip3", "pipx", "uv", "poetry", "conda",
    "npm", "npx", "yarn", "pnpm", "bun",
    "cargo", "go", "gem", "composer",
})

_ASK_NETWORK_HEADS = frozenset({
    "curl", "wget", "http", "httpie", "fetch",
    "ssh", "scp", "rsync", "ftp", "sftp",
})

_INTERPRETER_INLINE_OPTIONS = {
    "python": frozenset({"-c", "-m", "-"}),
    "python3": frozenset({"-c", "-m", "-"}),
    "py": frozenset({"-c", "-m", "-"}),
    "bash": frozenset({"-c", "-s", "-"}),
    "sh": frozenset({"-c", "-s", "-"}),
    "zsh": frozenset({"-c", "-s", "-"}),
    "node": frozenset({"-e", "--eval", "-p", "--print"}),
    "powershell": frozenset({"-command", "-c", "-encodedcommand", "-enc"}),
    "pwsh": frozenset({"-command", "-c", "-encodedcommand", "-enc"}),
    "cmd": frozenset({"/c", "/k"}),
}

# npm/yarn/pnpm 自动子命令 vs 需审批
_NPM_AUTO_SUBCMDS = frozenset({
    "run", "test", "start", "build", "lint", "format", "ci",
    "exec", "pack", "version", "outdated", "list", "ls", "view", "info",
})
_NPM_ASK_SUBCMDS = frozenset({
    "install", "i", "add", "uninstall", "remove", "rm", "update", "upgrade",
    "publish", "link", "unlink", "login", "logout",
})

_PIP_ASK_SUBCMDS = frozenset({
    "install", "uninstall", "download", "wheel",
})

_RISK_RANK = {"auto": 0, "ask": 1, "deny": 2}


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
    """workspace_auto（默认）| manual（每条 execute 都 ask，旧行为）。"""
    raw = os.getenv("EXECUTE_PROFILE", "workspace_auto").strip().lower()
    if raw in ("manual", "ask_all", "legacy"):
        return "manual"
    return "workspace_auto"


def _normalize_head(raw: str | None) -> str | None:
    if not raw:
        return None
    head = raw.strip().lower()
    # basename（兼容路径与 Windows 反斜杠）
    head = head.replace("\\", "/").rsplit("/", 1)[-1]
    # 去掉 .exe / .cmd / .bat / .ps1
    for suffix in (".exe", ".cmd", ".bat", ".ps1", ".com"):
        if head.endswith(suffix):
            head = head[: -len(suffix)]
            break
    # python3.11 → python3
    if re.fullmatch(r"python\d+(\.\d+)*", head):
        head = "python3" if head.startswith("python3") else "python"
    return head or None


def _segment_has_redirect(segment: str) -> bool:
    # 简单检测：引号外重定向较难，保守：含 > 或 < 且非比较运算符语境时升为 ask
    if re.search(r"(?<![-=])>(?!>)|(?<!<)<(?![<=])", segment):
        return True
    return False


def _is_cc_notification_script(segment: str, head: str, tokens: list[str]) -> bool:
    """识别 CC 消息 Skill，避免外部通知在 workspace_auto 下静默发送。"""
    if head not in {"python", "python3", "py"}:
        return False
    # python -c/-m/- 仍按解释器内联命令处理，不能被脚本路径规则误识别。
    inline_options = _INTERPRETER_INLINE_OPTIONS.get(head, frozenset())
    if any(token.lower() in inline_options for token in tokens[1:]):
        return False

    target_suffix = "skills/send-cc-msg/scripts/send_cc_msg.py"
    for token in tokens[1:]:
        candidate = token.strip().strip("\"'").replace("\\", "/").lower()
        if candidate == target_suffix or candidate.endswith("/" + target_suffix):
            return True

    # 兜底覆盖 Windows shell 对引号/反斜杠的切分差异。
    normalized = segment.replace("\\", "/").lower()
    return bool(
        re.search(
            r"(?:^|[\s/'\"])(?:[^\s/'\"]*/)?skills/send-cc-msg/scripts/send_cc_msg\.py(?=$|[\s'\"])",
            normalized,
        )
    )


def _classify_hard_deny(command: str) -> ExecuteClassification | None:
    if _COMMAND_SUBSTITUTION_PATTERN.search(command):
        return ExecuteClassification(
            effect="deny",
            reason="command_substitution",
            risk_note="命令含反引号或 $() 替换，硬拒绝且不可批准绕过。",
        )
    for pattern in _HARD_DENY_PATTERNS:
        m = pattern.search(command)
        if m:
            return ExecuteClassification(
                effect="deny",
                reason="hard_deny",
                risk_note=f"命中灾难性命令模式：{m.group(0)[:60]}",
                command_head=m.group(0)[:80],
            )
    return None


def _classify_segment(segment: str) -> ExecuteClassification:
    raw_tokens = _split_segment_tokens(segment)
    tokens = _tokens_after_env_assignments(list(raw_tokens))
    # 内联 env 赋值：Unix 风格，在 Windows cmd 下也偏危险 → ask
    if len(tokens) != len(raw_tokens):
        return ExecuteClassification(
            effect="ask",
            reason="env_assignment",
            risk_note="含内联环境变量赋值，需确认后执行。",
        )

    head_raw = _extract_command_head(segment)
    head = _normalize_head(head_raw)
    if head is None:
        return ExecuteClassification(
            effect="ask",
            reason="empty_or_unparsed",
            risk_note="无法解析命令头，需确认。",
        )

    if _is_cc_notification_script(segment, head, tokens):
        return ExecuteClassification(
            effect="ask",
            reason="external_notification",
            risk_note="CC 消息会产生外部通知副作用，发送前需要用户确认。",
            command_head=head,
        )

    # 解释器内联选项
    blocked = _INTERPRETER_INLINE_OPTIONS.get(head)
    if blocked:
        for tok in tokens[1:]:
            low = tok.lower()
            if low in blocked or (tok.startswith("-") and low.lstrip("-") in {b.lstrip("-") for b in blocked}):
                return ExecuteClassification(
                    effect="ask",
                    reason="interpreter_inline",
                    risk_note=(
                        f"`{head} {tok}` 可执行任意代码（非 OS 沙盒）。"
                        "批准后以当前用户权限运行；请确认内容安全。"
                    ),
                    command_head=head,
                )

    # 网络工具
    if head in _ASK_NETWORK_HEADS:
        return ExecuteClassification(
            effect="ask",
            reason="network",
            risk_note=f"`{head}` 可能访问网络，需确认。",
            command_head=head,
        )

    # pip / 包管理 install
    if head in ("pip", "pip3", "pipx", "uv", "poetry", "conda"):
        sub = tokens[1].lower() if len(tokens) > 1 else ""
        if sub in _PIP_ASK_SUBCMDS or sub == "pip" and len(tokens) > 2 and tokens[2].lower() in _PIP_ASK_SUBCMDS:
            return ExecuteClassification(
                effect="ask",
                reason="package_install",
                risk_note="包安装/卸载需确认。",
                command_head=head,
            )
        # uv run / poetry run 等 → ask（任意）
        if sub in ("run", "add", "remove", "sync", "tool"):
            return ExecuteClassification(
                effect="ask",
                reason="package_tool",
                risk_note=f"`{head} {sub}` 需确认。",
                command_head=head,
            )

    # npm / yarn / pnpm
    if head in ("npm", "npx", "yarn", "pnpm", "bun"):
        sub = tokens[1].lower() if len(tokens) > 1 else ""
        if head == "npx":
            # npx 默认拉取并执行包 → ask
            return ExecuteClassification(
                effect="ask",
                reason="npx_exec",
                risk_note="npx 可能下载并执行远程包，需确认。",
                command_head=head,
            )
        if sub in _NPM_ASK_SUBCMDS:
            return ExecuteClassification(
                effect="ask",
                reason="package_install",
                risk_note=f"`{head} {sub}` 会修改依赖或发包，需确认。",
                command_head=head,
            )
        if not sub or sub in _NPM_AUTO_SUBCMDS or sub.startswith("run"):
            return ExecuteClassification(
                effect="auto",
                reason="build_test",
                risk_note="已知构建/测试命令，工作区内自动执行。",
                command_head=head,
            )
        # npm 无子命令或未知 → ask
        return ExecuteClassification(
            effect="ask",
            reason="unknown_npm",
            risk_note=f"未知 `{head}` 子命令，需确认。",
            command_head=head,
        )

    # git
    if head == "git":
        sub = tokens[1].lower() if len(tokens) > 1 else ""
        if sub.startswith("-"):
            # git -C ... status
            for i, t in enumerate(tokens[1:], start=1):
                if not t.startswith("-"):
                    sub = t.lower()
                    break
            else:
                sub = ""
        if sub in _SAFE_GIT_SUBCMDS:
            return ExecuteClassification(
                effect="auto",
                reason="git_readonly",
                risk_note="只读 git 命令，自动执行。",
                command_head=head,
            )
        return ExecuteClassification(
            effect="ask",
            reason="git_mutating",
            risk_note=f"`git {sub or ''}` 可能修改仓库状态，需确认。",
            command_head=head,
        )

    # 只读探查
    if head in _AUTO_READONLY_HEADS:
        if _segment_has_redirect(segment):
            return ExecuteClassification(
                effect="ask",
                reason="redirect",
                risk_note="只读命令含重定向，需确认。",
                command_head=head,
            )
        return ExecuteClassification(
            effect="auto",
            reason="readonly",
            risk_note="只读探查，自动执行。",
            command_head=head,
        )

    # cd
    if head in _AUTO_CD_HEADS:
        return ExecuteClassification(
            effect="auto",
            reason="cd",
            risk_note="目录切换（越界由硬策略拦截）。",
            command_head=head,
        )

    # python / bash 脚本（非内联）：skills/*/scripts 自动放行，其它需确认
    if head in ("python", "python3", "py", "bash", "sh", "zsh"):
        from sandbox.path_rewriter import (
            _extract_bash_positional,
            _extract_python_positional,
            _to_posix,
        )

        def _is_skill_script_path(path: str) -> bool:
            norm = _to_posix(path).lstrip("./")
            # 兼容未被 shlex 吃掉反斜杠的 Windows 路径
            compact = path.replace("\\", "/")
            for candidate in (norm, compact, path):
                parts = candidate.replace("\\", "/").split("/")
                try:
                    si = parts.index("skills")
                except ValueError:
                    continue
                if (
                    len(parts) >= si + 4
                    and parts[si + 2] == "scripts"
                    and parts[si + 3]
                ):
                    return True
            return False

        # 先看原始 segment（避开 posix shlex 把 \ 当转义）
        if "skills" in segment.replace("\\", "/") and "/scripts/" in segment.replace(
            "\\", "/"
        ):
            return ExecuteClassification(
                effect="auto",
                reason="skill_script",
                risk_note="skills 自带脚本，自动执行。",
                command_head=head,
            )

        positional = None
        if head in ("python", "python3", "py"):
            positional = _extract_python_positional(segment)
        else:
            positional = _extract_bash_positional(segment)
        if positional and _is_skill_script_path(positional):
            return ExecuteClassification(
                effect="auto",
                reason="skill_script",
                risk_note="skills 自带脚本，自动执行。",
                command_head=head,
            )
        return ExecuteClassification(
            effect="ask",
            reason="script_exec",
            risk_note=(
                f"`{head}` 执行脚本需确认（非 skills 白名单脚本）。"
                "批准后以当前用户权限运行。"
            ),
            command_head=head,
        )

    # pytest / ruff 等无脚本参数的构建工具
    if head in _AUTO_BUILD_HEADS and head not in (
        "python", "python3", "py", "bash", "sh", "node", "npm", "npx",
    ):
        return ExecuteClassification(
            effect="auto",
            reason="build_test",
            risk_note="已知构建/测试工具，工作区内自动执行。",
            command_head=head,
        )

    # 未知 → ask
    return ExecuteClassification(
        effect="ask",
        reason="unknown_command",
        risk_note=f"命令 `{head}` 不在自动白名单，需确认后执行。",
        command_head=head,
    )


def classify_execute_command(command: str | None) -> ExecuteClassification:
    """对整条（可含 &&/||/;/|）命令分类；链式取最高风险。"""
    if not command or not str(command).strip():
        return ExecuteClassification(
            effect="ask",
            reason="empty",
            risk_note="空命令，需确认。",
        )
    cmd = str(command).strip()

    hard = _classify_hard_deny(cmd)
    if hard is not None:
        return hard

    # Windows 反斜杠路径：在 shlex(posix) 分段前先识别 skill 脚本，避免 \ 被当转义
    compact = cmd.replace("\\", "/")
    if "skills/" in compact and "/scripts/" in compact:
        head_guess = compact.split()[0].lower() if compact.split() else ""
        head_guess = head_guess.replace("\\", "/").rsplit("/", 1)[-1]
        for suffix in (".exe", ".cmd", ".bat"):
            if head_guess.endswith(suffix):
                head_guess = head_guess[: -len(suffix)]
        if head_guess.startswith("python") or head_guess in ("py", "bash", "sh", "zsh"):
            # 确认无内联 -c/-m
            if not any(f" {opt} " in f" {compact} " or compact.endswith(f" {opt}") for opt in ("-c", "-m", "-s")):
                if "skills/send-cc-msg/scripts/send_cc_msg.py" in compact.lower():
                    return ExecuteClassification(
                        effect="ask",
                        reason="external_notification",
                        risk_note="CC 消息会产生外部通知副作用，发送前需要用户确认。",
                        command_head=head_guess or "python",
                    )
                return ExecuteClassification(
                    effect="auto",
                    reason="skill_script",
                    risk_note="skills 自带脚本，自动执行。",
                    command_head=head_guess or "python",
                )

    segments = _split_into_segments(cmd)
    if not segments:
        return ExecuteClassification(
            effect="ask",
            reason="unparsed",
            risk_note="无法分段解析命令，需确认。",
        )

    worst = ExecuteClassification(effect="auto", reason="empty_chain", risk_note="")
    for seg in segments:
        c = _classify_segment(seg)
        if _RISK_RANK[c.effect] > _RISK_RANK[worst.effect]:
            worst = c
        elif c.effect == worst.effect and c.reason and not worst.risk_note:
            worst = c
    return worst


def classify_for_profile(
    command: str | None,
    *,
    profile: ExecuteProfile | None = None,
) -> ExecuteClassification:
    """应用 EXECUTE_PROFILE：manual 时除 deny 外一律 ask。"""
    base = classify_execute_command(command)
    prof = profile or execute_profile()
    if prof == "manual" and base.effect == "auto":
        return ExecuteClassification(
            effect="ask",
            reason="manual_profile",
            risk_note="当前为 manual 配置：每条 execute 均需确认。",
            command_head=base.command_head,
        )
    return base


def hitl_reason_for_ui(classification: ExecuteClassification) -> str:
    """给前端审批卡片的短说明。"""
    if classification.risk_note:
        return classification.risk_note
    return f"需要确认：{classification.reason}"
