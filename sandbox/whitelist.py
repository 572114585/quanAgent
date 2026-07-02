"""外层白名单安全拦截 + backend 单例组装。

从原 agent_runtime.py L992-1038（_build_rejection_response）+ L1041-1238
（_ShellWhitelistFilter 类）+ L1296-1302（backend 单例组装）拆出。

_SkillsShellBackend（内层）只做路径改写与编码兼容，不做命令形态拦截；本模块
的 _ShellWhitelistFilter（外层）负责：命令替换语法拦截、白名单 head 校验、
python -c / bash -c 内联代码拦截、cd 越界拦截、curl host 白名单拦截。放行后
转内层 backend 执行。

模块级 `backend` 单例由两层组装而成，供 agent_core.runtime.build_agent() 使用。
"""
import logging
from pathlib import Path
from typing import Iterable

from deepagents.backends import LocalShellBackend
from deepagents.backends.protocol import ExecuteResponse, SandboxBackendProtocol

from agent_core.config import WORKSPACE_ROOT
from sandbox.backend import _SkillsShellBackend
from sandbox.constants import (
    _CD_PATTERN,
    _COMMAND_SUBSTITUTION_PATTERN,
    DEFAULT_ALLOWED_COMMANDS,
    _NODE_BUILD_COMMANDS,
    _PYTHON_BLOCKED_OPTIONS,
    _REJECTION_EXIT_CODE,
    _SHELL_DENIED_MARKER,
)
from sandbox.path_rewriter import (
    _build_default_allow_pattern,
    _discover_skill_scripts,
    _extract_bash_positional,
    _extract_command_head,
    _extract_curl_urls,
    _extract_python_positional,
    _curl_urls_allowed,
    _path_stays_within_root,
    _rewrite_path_token,
    _split_into_segments,
    _split_segment_tokens,
    _to_posix,
    _tokens_after_env_assignments,
)

logger = logging.getLogger(__name__)


def _build_rejection_response(reason: str, command_head: str | None = None) -> ExecuteResponse:
    if reason == "command_substitution":
        output = f"{_SHELL_DENIED_MARKER} 命令含有命令替换语法（反引号或 $()），已被安全策略拦截。"
    elif reason == "env_assignment":
        output = f"{_SHELL_DENIED_MARKER} 命令含有内联环境变量赋值，已被安全策略拦截。"
    elif reason == "cwd_out_of_sandbox":
        output = (
            f"{_SHELL_DENIED_MARKER} 目标路径 `{command_head}` 超出工作目录根，已被拦截。"
            "请在 workspace 目录内操作。"
        )
    elif reason == "python_unsafe":
        output = (
            f"{_SHELL_DENIED_MARKER} Python 命令 `{command_head}` 含禁止选项（-c/-m/-），已被拦截。"
            "请直接调用 skill 脚本。"
        )
    elif reason == "python_script_not_allowed":
        output = (
            f"{_SHELL_DENIED_MARKER} Python 脚本 `{command_head}` 不在 skills 白名单内，已被拦截。"
            "禁止自写脚本——只能执行 skills 自带脚本："
            "skills/word-docx/scripts/{create,edit,view}.py、"
            "skills/excel-xlsx/scripts/{create,edit,view}.py。"
        )
    elif reason == "bash_unsafe":
        output = (
            f"{_SHELL_DENIED_MARKER} bash/sh 命令含禁止选项（-c/-s），已被拦截。"
            "禁止内联代码——请直接调用 skills 自带脚本。"
        )
    elif reason == "bash_script_not_allowed":
        output = (
            f"{_SHELL_DENIED_MARKER} bash/sh 脚本 `{command_head}` 不在 skills 白名单内，已被拦截。"
            "禁止自写脚本——只能执行 skills 自带脚本："
            "skills/web-video-presentation/scripts/scaffold.sh 等。"
        )
    elif reason == "curl_host_denied":
        output = (
            f"{_SHELL_DENIED_MARKER} curl 目标 URL `{command_head}` 的 host 不在白名单内，已被拦截。"
            "允许的 host：api.openai.com。"
        )
    elif reason == "not_in_allowlist" and command_head:
        output = (
            f"{_SHELL_DENIED_MARKER} 命令 `{command_head}` 不在白名单内，已被拦截。"
            "允许的命令：python/ls/dir/cat/type/head/tail/find/pwd/test/echo/"
            "cd/pushd/popd/chdir/npm/npx/node/bash/sh/jq/curl/zip。"
        )
    else:
        output = f"{_SHELL_DENIED_MARKER} 命令未通过安全校验，已被拦截。"
    return ExecuteResponse(output=output, exit_code=_REJECTION_EXIT_CODE, truncated=False)


class _ShellWhitelistFilter(SandboxBackendProtocol):
    """白名单安全包装：拦截命令替换/python -c/cd 越界/非白名单命令，放行后转内层。

    与 lesso 的 ShellCommandFilterMiddleware 的区别：
    - 去掉 skill 绑定、文件工具路径白名单、curl 联网策略（个人助手不需要）；
    - 保留命令替换拦截、白名单 head 校验、python -c 拦截、cd 沙箱。
    """

    def __init__(
        self,
        backend: LocalShellBackend,
        *,
        allow_commands: Iterable[str] | None = None,
        skills_root: str | None = None,
    ) -> None:
        self._backend = backend
        commands = (
            set(allow_commands) if allow_commands is not None else set(DEFAULT_ALLOWED_COMMANDS)
        )
        self._allow_pattern = _build_default_allow_pattern(commands)
        self._skills_root = Path(skills_root) if skills_root else backend.cwd
        # execute 脚本白名单：启动时 glob skills 自带脚本。python 后只能跟这些脚本。
        self._skill_scripts = _discover_skill_scripts(self._skills_root)

    @property
    def id(self) -> str:
        inner_id = getattr(self._backend, "id", None)
        return str(inner_id) if inner_id is not None else "shell-whitelist-filter"

    @property
    def cwd(self) -> Path:
        return getattr(self._backend, "cwd", self._skills_root)

    # 透传文件工具给内层（virtual_mode 映射由内层 FilesystemBackend 处理）
    def read(self, file_path, offset=0, limit=2000):
        return self._backend.read(file_path, offset=offset, limit=limit)

    def write(self, file_path, content):
        return self._backend.write(file_path, content)

    def edit(self, file_path, old_string, new_string, replace_all=False):
        return self._backend.edit(file_path, old_string, new_string, replace_all=replace_all)

    def ls(self, path):
        return self._backend.ls(path)

    def grep(self, pattern, path=None, glob=None):
        return self._backend.grep(pattern, path=path, glob=glob)

    def glob(self, pattern, path=None):
        return self._backend.glob(pattern, path=path)

    def upload_files(self, files):
        return self._backend.upload_files(files)

    def download_files(self, paths):
        return self._backend.download_files(paths)

    async def aread(self, file_path, offset=0, limit=2000):
        return await self._backend.aread(file_path, offset=offset, limit=limit)

    async def awrite(self, file_path, content):
        return await self._backend.awrite(file_path, content)

    async def aedit(self, file_path, old_string, new_string, replace_all=False):
        return await self._backend.aedit(file_path, old_string, new_string, replace_all=replace_all)

    async def als(self, path):
        return await self._backend.als(path)

    async def agrep(self, pattern, path=None, glob=None):
        return await self._backend.agrep(pattern, path=path, glob=glob)

    async def aglob(self, pattern, path=None):
        return await self._backend.aglob(pattern, path=path)

    async def aupload_files(self, files):
        return await self._backend.aupload_files(files)

    async def adownload_files(self, paths):
        return await self._backend.adownload_files(paths)

    # ----------------------------- shell -----------------------------
    def _reject_if_disallowed(self, command) -> ExecuteResponse | None:
        if not isinstance(command, str) or not command.strip():
            return None

        # 1. 命令替换语法拦截
        if _COMMAND_SUBSTITUTION_PATTERN.search(command):
            logger.warning("[shell_filter] 命令含命令替换语法被拒绝")
            return _build_rejection_response(reason="command_substitution")

        # 2. 逐段校验 head
        for segment in _split_into_segments(command):
            raw_tokens = _split_segment_tokens(segment)
            tokens = _tokens_after_env_assignments(list(raw_tokens))
            if len(tokens) != len(raw_tokens):
                logger.warning("[shell_filter] 命令含内联环境变量赋值被拒绝")
                return _build_rejection_response(reason="env_assignment")
            head = _extract_command_head(segment)
            if head is None:
                continue
            if not self._allow_pattern.fullmatch(head):
                logger.warning("[shell_filter] 命令未命中白名单: head=%s", head)
                return _build_rejection_response(reason="not_in_allowlist", command_head=head)
            # python -c/-m/- 拦截
            if head in {"python", "python3"}:
                for tok in tokens[1:]:
                    if tok in _PYTHON_BLOCKED_OPTIONS:
                        logger.warning("[shell_filter] python 危险选项被拒绝: %s", tok)
                        return _build_rejection_response(reason="python_unsafe", command_head=tok)
                # python 脚本白名单：第一个位置参数（脚本路径）必须在 skills 白名单内。
                # 路径先经 _rewrite_path_token 规范化（处理 /skills/...、D:\skills\...、
                # skills/... 等变形），再比对白名单集合，避免变形绕过。
                positional = _extract_python_positional(segment)
                if positional is not None and self._skill_scripts:
                    root_posix = _to_posix(str(self._skills_root))
                    root_win = str(self._skills_root)
                    rewritten = _rewrite_path_token(positional, root_posix, root_win)
                    candidate = rewritten if rewritten is not None else positional
                    # candidate 可能含反斜杠，统一成 POSIX 比对
                    candidate_norm = _to_posix(candidate)
                    if candidate_norm not in self._skill_scripts:
                        logger.warning(
                            "[shell_filter] python 脚本非白名单被拒绝: %s (normalized=%s)",
                            positional, candidate_norm,
                        )
                        return _build_rejection_response(
                            reason="python_script_not_allowed", command_head=positional,
                        )

            # bash/sh -c/-s 拦截（内联代码风险，仿 python -c 拦截）
            if head in {"bash", "sh"}:
                for tok in tokens[1:]:
                    if tok in {"-c", "-s"}:
                        logger.warning("[shell_filter] bash/sh 危险选项被拒绝: %s", tok)
                        return _build_rejection_response(reason="bash_unsafe", command_head=tok)
                # bash/sh 脚本白名单：第一个位置参数（脚本路径）必须在 skills 白名单内。
                # 路径规范化逻辑与 python 分支一致。
                positional = _extract_bash_positional(segment)
                if positional is not None and self._skill_scripts:
                    root_posix = _to_posix(str(self._skills_root))
                    root_win = str(self._skills_root)
                    rewritten = _rewrite_path_token(positional, root_posix, root_win)
                    candidate = rewritten if rewritten is not None else positional
                    candidate_norm = _to_posix(candidate)
                    if candidate_norm not in self._skill_scripts:
                        logger.warning(
                            "[shell_filter] bash/sh 脚本非白名单被拒绝: %s (normalized=%s)",
                            positional, candidate_norm,
                        )
                        return _build_rejection_response(
                            reason="bash_script_not_allowed", command_head=positional,
                        )

            # curl host 白名单拦截：只放行 _CURL_ALLOWED_HOSTS 中的 host
            if head == "curl":
                urls = _extract_curl_urls(segment)
                allowed, denied_url = _curl_urls_allowed(urls)
                if not allowed:
                    logger.warning(
                        "[shell_filter] curl host 白名单拒绝: url=%s", denied_url,
                    )
                    return _build_rejection_response(
                        reason="curl_host_denied", command_head=denied_url,
                    )

        # 3. cd/pushd/chdir 目标越界拦截（路径改写后再校验）
        if self._skills_root:
            for cd_match in _CD_PATTERN.finditer(command):
                target = cd_match.group("target").strip().strip('"').strip("'")
                if not target:
                    continue
                # 先做路径改写再判越界（与内层 _normalize_command_paths 一致）
                root_posix = _to_posix(str(self._skills_root))
                root_win = str(self._skills_root)
                rewritten = _rewrite_path_token(target, root_posix, root_win)
                check_target = rewritten if rewritten is not None else target
                if not _path_stays_within_root(check_target, self._skills_root):
                    logger.warning(
                        "[shell_filter] cd 越界拒绝: target=%s, root=%s",
                        target, self._skills_root,
                    )
                    return _build_rejection_response(reason="cwd_out_of_sandbox", command_head=target)
        return None

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        rejection = self._reject_if_disallowed(command)
        if rejection is not None:
            return rejection
        return self._backend.execute(command, timeout=timeout)

    async def aexecute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        rejection = self._reject_if_disallowed(command)
        if rejection is not None:
            return rejection
        return await self._backend.aexecute(command, timeout=timeout)


# ---------------------------------------------------------------------------
# backend 单例组装（原 agent_runtime.py L1296-1302）
# 外层白名单 + 内层路径改写/编码。root_dir 保持 "workspace" 字面值
# （改为从 agent_core.config.WORKSPACE_ROOT 取，值不变）。
# ---------------------------------------------------------------------------
_inner_backend = _SkillsShellBackend(root_dir=str(WORKSPACE_ROOT), virtual_mode=True)
backend = _ShellWhitelistFilter(
    _inner_backend,
    allow_commands=DEFAULT_ALLOWED_COMMANDS | _NODE_BUILD_COMMANDS,
    skills_root=str(_inner_backend.cwd),
)
