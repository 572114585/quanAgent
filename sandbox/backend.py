"""内层 Shell 后端：execute 前做 token 级路径改写 + 编码兼容，并对写操作做路径沙箱。

从原 agent_runtime.py L719-943 拆出（_SkillsShellBackend 类）。

为什么需要这一层：
deepagents 的 LocalShellBackend(virtual_mode=True) 只对 read_file/write_file
等文件工具做虚拟路径映射（/foo → root_dir/foo），而 execute() 直接把命令
原样丢给 shell（cwd=root_dir），不做任何 /foo → root_dir/foo 的转换。于是
SKILL.md 里写的 /skills/... 在 execute 下会被 shell 当成系统绝对路径（Windows
上解析成 D:\\skills\\...），脚本找不到。

本类重写 execute/aexecute：先做 _normalize_command_paths 路径改写，再用精简环境
跑子进程，并做 utf-8/gbk 双解码。同时重写 write/edit/upload_files：写操作只允许
output/ 子树，skills/ 子树完全只读（防模型自写脚本污染 skill 目录）。
"""
import asyncio
import logging
import subprocess

from deepagents.backends import LocalShellBackend
from deepagents.backends.protocol import (
    EditResult,
    ExecuteResponse,
    FileUploadResponse,
    WriteResult,
)

from sandbox.constants import _SHELL_DENIED_MARKER, _SKILLS_SUBDIR, _WRITE_ALLOWED_SUBDIRS
from sandbox.path_rewriter import (
    _build_skill_subprocess_env,
    _decode_shell_output,
    _normalize_command_paths,
    _path_under_subdir,
)

logger = logging.getLogger(__name__)


class _SkillsShellBackend(LocalShellBackend):
    """LocalShellBackend 子类：execute 前做 token 级路径改写 + 编码兼容，
    并对 write/edit/upload_files 做写路径沙箱。

    - execute()：重写，做路径改写 + utf-8/gbk 解码兜底（详见方法注释）。
    - write/edit/upload_files：重写，在调父类前校验目标路径——写操作只允许
      output/ 子树，skills/ 子树完全只读（防模型自写脚本污染 skill 目录）。
      read/ls/grep/glob/download_files 不重写，沿用父类 virtual_mode 行为
      （只读探查不受限）。
    """

    # ----------------------------- 写路径沙箱 -----------------------------
    def _check_write_target(self, file_path: str):
        """校验写入目标路径是否合法。返回 (resolved_path, None) 或 (None, error_msg)。

        规则（路径先经父类 _resolve_path 解析成绝对路径再判，防相对越界）：
        - 落在 output/ 子树 → 允许；
        - 落在 skills/ 子树 → 拒绝（只读保护）；
        - 其他位置 → 拒绝（写操作只允许 output/）。
        解析失败（路径非法/越界 root）→ 拒绝。
        """
        try:
            resolved = self._resolve_path(file_path)
        except (OSError, RuntimeError, ValueError) as e:
            return None, f"Error writing file '{file_path}': {e}"

        if _path_under_subdir(resolved, self.cwd, _SKILLS_SUBDIR):
            return None, (
                f"{_SHELL_DENIED_MARKER} 拒绝写入 skills/ 子树（skills 只读，"
                f"保护脚本不被污染）。路径: {file_path}。写操作只允许 output/ 子树。"
            )
        for allowed in _WRITE_ALLOWED_SUBDIRS:
            if _path_under_subdir(resolved, self.cwd, allowed):
                return resolved, None
        return None, (
            f"{_SHELL_DENIED_MARKER} 拒绝写入非 output/ 路径: {file_path}。"
            "写操作只允许 output/ 子树。"
        )

    def write(self, file_path: str, content: str):  # type: ignore[override]
        resolved, err = self._check_write_target(file_path)
        if err is not None:
            return WriteResult(error=err)
        # 复用父类 write（已含"已存在则拒绝"、O_NOFOLLOW、mkdir parents 等逻辑）。
        return super().write(file_path, content)

    def edit(self, file_path: str, old_string: str, new_string, replace_all: bool = False):  # type: ignore[override]
        resolved, err = self._check_write_target(file_path)
        if err is not None:
            return EditResult(error=err)
        return super().edit(file_path, old_string, new_string, replace_all=replace_all)

    def upload_files(self, files):  # type: ignore[override]
        """批量上传：逐个校验路径，拒绝的项标 error，允许的交父类写。

        FileUploadResponse.error 是 Literal 枚举（不能塞自定义消息），所以拒绝时
        用 permission_denied，并把可读原因记到日志（模型从外层 wrapper 看不到详细
        原因时，可改用 write_file 单文件路径获取完整消息）。
        """
        responses = []
        for path, content in files:
            resolved, err = self._check_write_target(path)
            if err is not None:
                logger.warning("[file_guard] upload 拒绝: %s", err)
                responses.append(FileUploadResponse(path=path, error="permission_denied"))
            else:
                # 单文件交父类处理（父类 upload_files 接 list，逐个调以混合错误）。
                parent_resp = super().upload_files([(path, content)])
                responses.extend(parent_resp)
        return responses

    async def awrite(self, file_path: str, content: str):  # type: ignore[override]
        return self.write(file_path, content)

    async def aedit(self, file_path: str, old_string: str, new_string, replace_all: bool = False):  # type: ignore[override]
        return self.edit(file_path, old_string, new_string, replace_all=replace_all)

    async def aupload_files(self, files):  # type: ignore[override]
        return self.upload_files(files)

    # ----------------------------- execute -----------------------------
    def execute(self, command: str, *, timeout: int | None = None):  # type: ignore[override]
        if not command or not isinstance(command, str):
            return ExecuteResponse(
                output="Error: Command must be a non-empty string.",
                exit_code=1,
                truncated=False,
            )

        normalized = _normalize_command_paths(command, self.cwd)

        effective_timeout = timeout if timeout is not None else self._default_timeout
        if effective_timeout <= 0:
            raise ValueError(f"timeout must be positive, got {effective_timeout}")

        env = _build_skill_subprocess_env()

        try:
            result = subprocess.run(
                normalized,
                check=False,
                shell=True,
                capture_output=True,
                stdin=subprocess.DEVNULL,
                text=False,
                timeout=effective_timeout,
                env=env,
                cwd=str(self.cwd),
            )
            stdout = _decode_shell_output(result.stdout)
            stderr = _decode_shell_output(result.stderr)

            output_parts = []
            if stdout:
                output_parts.append(stdout)
            if stderr:
                stderr_lines = stderr.strip().split("\n")
                output_parts.extend(f"[stderr] {line}" for line in stderr_lines)

            output = "\n".join(output_parts) if output_parts else "<no output>"
            truncated = False
            if len(output) > self._max_output_bytes:
                output = output[: self._max_output_bytes]
                output += f"\n\n... Output truncated at {self._max_output_bytes} bytes."
                truncated = True
            if result.returncode != 0:
                output = f"{output.rstrip()}\n\nExit code: {result.returncode}"

            return ExecuteResponse(
                output=output,
                exit_code=result.returncode,
                truncated=truncated,
            )
        except subprocess.TimeoutExpired:
            if timeout is not None:
                msg = f"Error: Command timed out after {effective_timeout} seconds (custom timeout). The command may be stuck or require more time."
            else:
                msg = f"Error: Command timed out after {effective_timeout} seconds. For long-running commands, re-run using the timeout parameter."
            return ExecuteResponse(output=msg, exit_code=124, truncated=False)
        except Exception as exc:
            return ExecuteResponse(
                output=f"Error executing command ({type(exc).__name__}): {exc}",
                exit_code=1,
                truncated=False,
            )

    async def aexecute(self, command: str, *, timeout: int | None = None):  # type: ignore[override]
        # 必须真正异步：entrypoints/web.py 的 SSE 路径走 astream → aexecute。
        # 若直接转调同步 subprocess.run，会阻塞 asyncio 事件循环，
        # 导致 sse_starlette 无法及时 flush 数据到前端（token 延迟堆积）。
        # 用 asyncio.create_subprocess_shell 真异步执行（保留 shell 语义以支持 &&/||/cd 链）。
        if not command or not isinstance(command, str):
            return ExecuteResponse(
                output="Error: Command must be a non-empty string.",
                exit_code=1,
                truncated=False,
            )

        normalized = _normalize_command_paths(command, self.cwd)

        effective_timeout = timeout if timeout is not None else self._default_timeout
        if effective_timeout <= 0:
            raise ValueError(f"timeout must be positive, got {effective_timeout}")

        env = _build_skill_subprocess_env()

        try:
            proc = await asyncio.create_subprocess_shell(
                normalized,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.DEVNULL,
                cwd=str(self.cwd),
                env=env,
            )
        except Exception as exc:
            return ExecuteResponse(
                output=f"Error spawning command ({type(exc).__name__}): {exc}",
                exit_code=1,
                truncated=False,
            )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=effective_timeout
            )
            returncode = proc.returncode
        except asyncio.TimeoutError:
            # 杀掉超时子进程，避免僵尸
            try:
                if proc.returncode is None:
                    proc.kill()
                    await proc.wait()
            except Exception:
                pass
            if timeout is not None:
                msg = f"Error: Command timed out after {effective_timeout} seconds (custom timeout). The command may be stuck or require more time."
            else:
                msg = f"Error: Command timed out after {effective_timeout} seconds. For long-running commands, re-run using the timeout parameter."
            return ExecuteResponse(output=msg, exit_code=124, truncated=False)

        stdout = _decode_shell_output(stdout_bytes)
        stderr = _decode_shell_output(stderr_bytes)

        output_parts: list[str] = []
        if stdout:
            output_parts.append(stdout)
        if stderr:
            stderr_lines = stderr.strip().split("\n")
            output_parts.extend(f"[stderr] {line}" for line in stderr_lines)

        output = "\n".join(output_parts) if output_parts else "<no output>"
        truncated = False
        if len(output) > self._max_output_bytes:
            output = output[: self._max_output_bytes]
            output += f"\n\n... Output truncated at {self._max_output_bytes} bytes."
            truncated = True
        if returncode != 0:
            output = f"{output.rstrip()}\n\nExit code: {returncode}"

        return ExecuteResponse(
            output=output,
            exit_code=returncode,
            truncated=truncated,
        )
