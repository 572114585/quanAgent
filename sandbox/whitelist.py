"""外层删除策略安全拦截 + backend 单例组装。

从原 agent_runtime.py L992-1038（_build_rejection_response）+ L1041-1238
（_ShellWhitelistFilter 类）+ L1296-1302（backend 单例组装）拆出。

_SkillsShellBackend（内层）只做路径改写与编码兼容，不做命令形态拦截；本模块
的 _ShellWhitelistFilter（外层）负责：

- 硬拒绝（永不绕过）：可识别删除命令、cd 越界

命令形态级删除检测不解析任意脚本或解释器内部的文件系统 API。
信任级别经 sandbox.trust ContextVar 传递。

模块级 `backend` 单例由两层组装而成，供 agent_core.runtime.build_agent() 使用。
"""
import logging
import threading
import time
from pathlib import Path
from typing import Iterable

from deepagents.backends import LocalShellBackend
from deepagents.backends.protocol import ExecuteResponse, SandboxBackendProtocol

from agent_core.config import WORKSPACE_ROOT
from sandbox.backend import _SkillsShellBackend
from sandbox.constants import _CD_PATTERN, _REJECTION_EXIT_CODE, _SHELL_DENIED_MARKER
from sandbox.path_rewriter import _path_stays_within_root, _rewrite_path_token, _to_posix
from sandbox.trust import TrustLevel, get_execute_trust_level

logger = logging.getLogger(__name__)

_SKILL_DOWNLOAD_CACHE: dict[tuple[str, ...], tuple[float, list]] = {}
_SKILL_DOWNLOAD_CACHE_LOCK = threading.Lock()
_SKILL_DOWNLOAD_CACHE_TTL = 300.0


def _build_rejection_response(reason: str, command_head: str | None = None) -> ExecuteResponse:
    if reason == "delete_command":
        output = (
            f"{_SHELL_DENIED_MARKER} 命令包含可识别的删除操作，已被安全策略拦截。"
            "删除命令不支持通过审批或 always-approve 绕过。"
        )
    elif reason == "cwd_out_of_sandbox":
        output = (
            f"{_SHELL_DENIED_MARKER} 目标路径 `{command_head}` 超出工作目录根，已被拦截。"
            "请在 workspace 目录内操作。"
        )
    else:
        output = f"{_SHELL_DENIED_MARKER} 命令未通过安全校验，已被拦截。"
    return ExecuteResponse(output=output, exit_code=_REJECTION_EXIT_CODE, truncated=False)


class _ShellWhitelistFilter(SandboxBackendProtocol):
    """删除策略安全包装：删除命令拒绝，其他命令转发到底层。"""

    def __init__(
        self,
        backend: LocalShellBackend,
        *,
        allow_commands: Iterable[str] | None = None,
        skills_root: str | None = None,
    ) -> None:
        self._backend = backend
        # 保留 allow_commands 参数以兼容已有调用方；命令白名单不再参与执行。
        self._skills_root = Path(skills_root) if skills_root else backend.cwd

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
        key = tuple(str(path) for path in paths)
        if key and all(path.endswith("/SKILL.md") or path.endswith("\\SKILL.md") for path in key):
            with _SKILL_DOWNLOAD_CACHE_LOCK:
                cached = _SKILL_DOWNLOAD_CACHE.get(key)
                if cached and time.monotonic() - cached[0] < _SKILL_DOWNLOAD_CACHE_TTL:
                    return cached[1]
            result = self._backend.download_files(paths)
            with _SKILL_DOWNLOAD_CACHE_LOCK:
                _SKILL_DOWNLOAD_CACHE[key] = (time.monotonic(), result)
            return result
        return self._backend.download_files(paths)

    def inspect_file(self, file_path, *, tail_lines=0, count_literals=None):
        return self._backend.inspect_file(
            file_path,
            tail_lines=tail_lines,
            count_literals=count_literals,
        )

    def replace_file(self, file_path, content):
        return self._backend.replace_file(file_path, content)

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
        key = tuple(str(path) for path in paths)
        if key and all(path.endswith("/SKILL.md") or path.endswith("\\SKILL.md") for path in key):
            with _SKILL_DOWNLOAD_CACHE_LOCK:
                cached = _SKILL_DOWNLOAD_CACHE.get(key)
                if cached and time.monotonic() - cached[0] < _SKILL_DOWNLOAD_CACHE_TTL:
                    return cached[1]
            result = await self._backend.adownload_files(paths)
            with _SKILL_DOWNLOAD_CACHE_LOCK:
                _SKILL_DOWNLOAD_CACHE[key] = (time.monotonic(), result)
            return result
        return await self._backend.adownload_files(paths)

    async def ainspect_file(self, file_path, *, tail_lines=0, count_literals=None):
        return await self._backend.ainspect_file(
            file_path,
            tail_lines=tail_lines,
            count_literals=count_literals,
        )

    async def areplace_file(self, file_path, content):
        return await self._backend.areplace_file(file_path, content)

    # ----------------------------- shell -----------------------------
    def _hard_reject(self, command: str) -> ExecuteResponse | None:
        """永不绕过的硬拒绝：删除命令、cd 越界。"""
        from agent_core.execute_policy import classify_execute_command

        classification = classify_execute_command(command)
        if classification.reason == "delete_command":
            logger.warning("[shell_filter] 删除命令被拒绝: %s", command[:120])
            return _build_rejection_response(reason="delete_command")

        if self._skills_root:
            for cd_match in _CD_PATTERN.finditer(command):
                target = cd_match.group("target").strip().strip('"').strip("'")
                if not target:
                    continue
                root_posix = _to_posix(str(self._skills_root))
                root_win = str(self._skills_root)
                rewritten = _rewrite_path_token(target, root_posix, root_win)
                check_target = rewritten if rewritten is not None else target
                if not _path_stays_within_root(check_target, self._skills_root):
                    logger.warning(
                        "[shell_filter] cd 越界拒绝: target=%s, root=%s",
                        target, self._skills_root,
                    )
                    return _build_rejection_response(
                        reason="cwd_out_of_sandbox", command_head=target
                    )
        return None

    def _reject_if_disallowed(
        self,
        command: str,
        *,
        trust_level: TrustLevel | None = None,
    ) -> ExecuteResponse | None:
        if not isinstance(command, str) or not command.strip():
            return None

        hard = self._hard_reject(command)
        if hard is not None:
            logger.warning(
                "[shell_filter] hard_reject trust=%s cmd=%s",
                trust_level if trust_level is not None else get_execute_trust_level(),
                command[:80],
            )
            return hard
        # 非删除命令不再经过白名单、解释器、联网或环境变量软限制。
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
    skills_root=str(_inner_backend.cwd),
)
