"""
共享的 agent 运行时。

CLI（demo.py）保留不动；WeCom 渠道（run_wecom.py）从这里 import 同一个 agent。
注意：WeCom 没有 stdin，**不启用** interrupt_on={...}（HITL 在企业微信里会卡死）。
"""
import logging
import os
import re
import shlex
import subprocess
import uuid
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Iterable

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langfuse import get_client
from langfuse.langchain import CallbackHandler
from langgraph.checkpoint.memory import MemorySaver
from deepagents import create_deep_agent
from deepagents.backends import LocalShellBackend
from deepagents.backends.protocol import (
    EditResult,
    ExecuteResponse,
    FileUploadResponse,
    SandboxBackendProtocol,
    WriteResult,
)

from ducktools import web_search
from html_tools import render_html
from time_tools import get_current_time

load_dotenv()

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Skill shell backend: 白名单 + token 级路径改写 + 编码兼容
#
# 为什么需要这一层：
# deepagents 的 LocalShellBackend(virtual_mode=True) 只对 read_file/write_file
# 等文件工具做虚拟路径映射（/foo → root_dir/foo），而 execute() 直接把命令
# 原样丢给 shell（cwd=root_dir），不做任何 /foo → root_dir/foo 的转换。于是
# SKILL.md 里写的 /skills/... 在 execute 下会被 shell 当成系统绝对路径（Windows
# 上解析成 D:\skills\...），脚本找不到。
#
# 解决方案融合了 lesso 项目和 token 级改写两种思路：
# - 外层 _ShellWhitelistFilter：白名单收窄命令形态（拦命令替换/python -c/cd 越界），
#   取 lesso 的安全收敛；
# - 内层 _SkillsShellBackend：用 shlex 逐 token 改写路径（比 lesso 的全局 replace
#   健壮，不误伤 JSON 参数、不漏 --out 末尾路径），前缀从 root_dir 动态推导（不
#   硬编码 C:/skills/），换机器自动适应；
# - 编码：utf-8/gbk 双解码 + 强制 PYTHONUTF8=1（取 lesso，解决中文乱码）。
# 两层共用 shlex 拆词。
# ---------------------------------------------------------------------------


# 默认放行的 shell 命令白名单。
# - python/python3：跑 skill 脚本必需（-c/-m 被单独拦截防内联代码）。
# - 只读探查类（ls/dir/cat/type/head/tail/find/pwd/test/echo）：模型探查目录结构用，
#   无写入/网络副作用，物理工作目录受 root_dir 锁定。
# - 目录切换类（cd/pushd/popd/chdir）：目标经路径改写后必须在 root_dir 子树内，
#   越界由 cd 沙箱校验拦截。
DEFAULT_ALLOWED_COMMANDS: frozenset[str] = frozenset(
    {
        "python",
        "python3",
        "ls",
        "dir",
        "cat",
        "type",
        "head",
        "tail",
        "find",
        "pwd",
        "test",
        "echo",
        "cd",
        "pushd",
        "popd",
        "chdir",
    }
)

# 拦截的命令替换语法：反引号、$()。
_COMMAND_SUBSTITUTION_PATTERN = re.compile(r"`|\$\(")
# python 危险选项：-c（内联代码）、-m（模块）、-（stdin）。
_PYTHON_BLOCKED_OPTIONS = frozenset({"-c", "-m", "-"})
# 引号外的链式命令分隔符。
_CHAIN_SEPARATORS: frozenset[str] = frozenset({"&&", "||", ";", "|", "&", "\n"})
# 命令中显式指定 cwd 的常见模式：cd /xxx、pushd /xxx、chdir /xxx。
_CD_PATTERN = re.compile(r"\b(?:cd|pushd|chdir)\s+(?P<target>[^\s;&|]+)")
# 子进程环境白名单：只放行这些键（其余不继承），再强制 UTF-8。
_SAFE_SUBPROCESS_ENV_KEYS: tuple[str, ...] = (
    "PATH",
    "SystemRoot",
    "WINDIR",
    "COMSPEC",
    "PATHEXT",
    "TEMP",
    "TMP",
)
# 标记"输出路径"的参数名：下一个 token 必定是路径，强制改写。
_PATH_VALUE_FLAGS: frozenset[str] = frozenset(
    {
        "--out",
        "--file",
        "-o",
        "--output",
        "--append-paragraphs",
        "--append-bullets",
        "--append-blocks",
        "--add-heading",
        "--replace",
    }
)
_REJECTION_EXIT_CODE = 126
_SHELL_DENIED_MARKER = "[E_SHELL_DENIED]"
# 写操作唯一允许的子树（相对 root_dir）：模型产出只能落这里。
# skills/ 子树完全只读，保护脚本不被模型自写文件污染。
_WRITE_ALLOWED_SUBDIRS: tuple[str, ...] = ("output", "tmp")
# skills 子树名（写保护边界）。
_SKILLS_SUBDIR = "skills"
# skills 脚本的 glob 模式（相对 root_dir），用于构建 execute 脚本白名单。
_SKILL_SCRIPTS_GLOB = "skills/*/scripts/*.py"


# ----------------------------- shlex 分段 / head 提取 -----------------------------
# 这一组函数取自 lesso 的 shell_command_filter_middleware，是经过验证的引号感知分段。


def _split_into_segments(command: str) -> list[str]:
    """按 shell 链接符切分命令，但跳过引号内容。

    用 shlex 流式解析：遇到引号外的 ; / && / || / | / & / 换行 即视为段终止。
    lexer 失败（罕见，如未闭合引号）时回退到 re.split，保守降级（误拦比误放更安全）。
    """
    return [seg for seg in _split_into_segments_with_seps(command)[0]]


def _split_into_segments_with_seps(command: str) -> tuple[list[str], list[str]]:
    """同 _split_into_segments，但同时返回段之间的分隔符列表（用于无损重组）。

    Returns:
        (segments, separators)：segments 有 N 段，separators 有 N-1 个分隔符。
        segments[i] + separators[i] + segments[i+1] + ... 还原原命令（空白可能有差异）。
    """
    text = command or ""
    if not text.strip():
        return [], []

    try:
        lex = shlex.shlex(text, posix=True, punctuation_chars="&|;")
        lex.whitespace_split = True
        tokens = list(lex)
    except ValueError:
        fallback = re.split(r"(&&|\|\||;|\||&|\n)", text)
        segments: list[str] = []
        seps: list[str] = []
        for i, part in enumerate(fallback):
            if i % 2 == 0:
                if part.strip():
                    segments.append(part.strip())
            else:
                if segments:
                    seps.append(part)
        return segments, seps

    segments2: list[list[str]] = [[]]
    seps2: list[str] = []
    for tok in tokens:
        if tok in _CHAIN_SEPARATORS:
            if segments2[-1]:
                segments2.append([])
                seps2.append(tok)
            continue
        segments2[-1].append(tok)

    out_segs: list[str] = []
    for seg in segments2:
        if not seg:
            continue
        try:
            out_segs.append(shlex.join(seg))
        except Exception:
            out_segs.append(" ".join(seg))
    return out_segs, seps2


def _split_segment_tokens(segment: str) -> list[str]:
    """单段命令拆成 token 列表（引号感知）。"""
    try:
        return shlex.split(segment, comments=False, posix=True)
    except ValueError:
        return segment.split()


def _tokens_after_env_assignments(tokens: list[str]) -> list[str]:
    """剥掉开头的环境变量赋值（FOO=bar），返回剩余 token。"""
    while tokens:
        token = tokens[0]
        if "=" in token and token.split("=", 1)[0].isidentifier():
            tokens = tokens[1:]
            continue
        break
    return tokens


def _extract_command_head(segment: str) -> str | None:
    """提取段命令的 head（剥环境赋值 + 取 basename，兼容 python3.11 这类）。"""
    tokens = _split_segment_tokens(segment)
    tokens = _tokens_after_env_assignments(tokens)
    while tokens:
        head = tokens[0]
        if "=" in head and head.split("=", 1)[0].isidentifier():
            tokens = tokens[1:]
            continue
        return head.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    return None


# python 解释器选项中"带值"的：下一个 token 是值（不是位置参数），跳过。
# 覆盖 -W/-X/-c/-m（-c/-m 已被 _PYTHON_BLOCKED_OPTIONS 拦截，这里列全以防遗漏）。
_PYTHON_VALUE_OPTIONS: frozenset[str] = frozenset({"-c", "-m", "-W", "-X"})
# python "无值"选项（标志位）：单独一个 token，不消费下一个。
# 包含 -B/-d/-E/-O/-OO/-s/-S/-u/-v 等；长选项 --check-hash-based-pycs=val 自带值。
_PYTHON_FLAG_OPTIONS: frozenset[str] = frozenset(
    {
        "-b", "-B", "-d", "-E", "-I", "-O", "-OO", "-P", "-q",
        "-s", "-S", "-u", "-v", "-V", "-h", "--help", "--version",
    }
)


def _extract_python_positional(segment: str) -> str | None:
    """从 `python [opts] script.py [args]` 段提取第一个位置参数（脚本路径）。

    跳过解释器选项（-O/-u 等）及带值选项（-W/-X/-c/-m）的值。返回脚本 token
    原样字符串（含引号则剥掉），无位置参数（如 `python --help`）返回 None。
    """
    tokens = _split_segment_tokens(segment)
    tokens = _tokens_after_env_assignments(tokens)
    if not tokens:
        return None
    # tokens[0] 是 python/python3.x，从 [1:] 开始扫选项。
    i = 1
    n = len(tokens)
    while i < n:
        tok = tokens[i]
        # 带值选项：跳过它和下一个 token（值）
        if tok in _PYTHON_VALUE_OPTIONS:
            i += 2
            continue
        # 形如 --opt=value / -X opt_value（-X utf8 这种合并形式）→ 单 token，跳过
        if tok.startswith("--") and "=" in tok:
            i += 1
            continue
        # 无值标志位 → 跳过
        if tok in _PYTHON_FLAG_OPTIONS or tok.startswith("-"):
            # 任何以 - 开头的都当选项跳过（保守：宁可误判选项也不误判成脚本）
            i += 1
            continue
        # 第一个非选项 token = 位置参数（脚本路径），剥外层引号
        if len(tok) >= 2 and tok[0] in ('"', "'") and tok[-1] == tok[0]:
            return tok[1:-1]
        return tok
    return None


def _build_default_allow_pattern(commands: Iterable[str]) -> re.Pattern[str]:
    alternatives = "|".join(re.escape(cmd) for cmd in sorted(set(commands)))
    if not alternatives:
        return re.compile(r"^$")
    return re.compile(rf"^(?:{alternatives})$")


def _discover_skill_scripts(root: Path) -> frozenset[str]:
    """启动时 glob `<root>/skills/*/scripts/*.py`，返回相对 root 的 POSIX 路径集合。

    这是 execute 脚本白名单的来源——deepagents 无 skills 脚本注册表，必须自己扫。
    每次启动重新扫，所以新增 skill 脚本重启即生效（无需改代码）。
    """
    scripts_dir = root / _SKILLS_SUBDIR
    if not scripts_dir.is_dir():
        return frozenset()
    found: set[str] = set()
    for p in scripts_dir.glob("*/scripts/*.py"):
        try:
            rel = p.resolve().relative_to(root.resolve())
            found.add(_to_posix(str(rel)))
        except (ValueError, OSError):
            continue
    return frozenset(found)


# ----------------------------- token 级路径改写 -----------------------------


def _is_absolute_path(p: str) -> bool:
    if not p:
        return False
    return PurePosixPath(p).is_absolute() or PureWindowsPath(p).is_absolute()


def _is_url(p: str) -> bool:
    return bool(p) and (
        p.startswith(("http://", "https://", "ftp://"))
        or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", p) is not None
    )


def _to_posix(p: str) -> str:
    return p.replace("\\", "/")


def _rewrite_path_token(token: str, root_posix: str, root_win: str) -> str | None:
    """把一个路径 token 改写成相对 root_dir 的路径。

    返回改写后的相对路径字符串；若该 token 不是需要改写的路径则返回 None。
    规则：
    - 以 root_dir 为前缀（POSIX 或 Windows 形式）→ 剥成相对路径；
    - /skills/... /output/... 这类虚拟绝对路径 → 剥成 skills/... output/...；
    - root 所在盘的盘符根路径 X:\\create.py / X:\\skills\\... → 剥掉 "X:\\"
      当作 workspace 虚拟根下的相对路径（execute 不做虚拟映射，需在此兜底）；
      其他盘符的绝对路径（C:\\Windows 等）不动，交给沙箱拦截；
    - 已经是相对路径 / URL / 纯值 → 不动（返回 None）。
    """
    if not token or _is_url(token):
        return None

    text = token
    lowered = text.lower()

    # 完整 root_dir 前缀（POSIX / Windows 两种形式）
    for prefix in (root_posix + "/", root_posix, root_win + "\\", root_win):
        if prefix and lowered.startswith(prefix.lower()):
            rest = text[len(prefix):]
            return rest.lstrip("/\\") or None

    # 虚拟绝对路径：/skills/... /output/...
    # （这些都是 root_dir 下的已知子目录，剥掉前导 / 即可相对化）
    for virt in ("/skills/", "/output/"):
        if lowered.startswith(virt):
            return text[1:]  # 去掉前导 /

    # 盘符绝对路径：X:\foo\bar 或 X:/foo/bar。
    # deepagents 的 execute() 不做虚拟路径映射，于是 SKILL 里写的 /create.py 在
    # Windows cmd.exe 下会被解析成「当前盘根」D:\create.py（而非 workspace 根下的
    # create.py），导致脚本找不到。模型也会直接写 D:\create.py 这种盘符根路径，
    # 本意仍是 workspace 根下的文件。
    #
    # 收敛策略（只动 root 所在盘的盘符根路径，其他盘符原样保留）：
    # - 盘符 == root 所在盘：剥掉 "X:\" 前缀，当作 workspace 虚拟根下的相对路径
    #   （D:\skills\create.py → skills/create.py；D:\output\r.docx → output/r.docx）。
    #   这样既覆盖"误解析的虚拟路径"，也覆盖"模型直接写的盘符根路径"，且不会
    #   把 root 真子树（D:\project\workspace\...）误判——那部分已被上面的 root
    #   前缀分支处理掉了。
    # - 盘符 != root 所在盘（C:\Windows、E:\xxx）：不动，交给后续 cd 沙箱 / 白名单拦截。
    root_drive = Path(root_win).drive  # 形如 "D:"
    m = re.match(r"^([A-Za-z]:)[/\\](.+)$", text)
    if m and m.group(1).lower() == root_drive.lower():
        rest = m.group(2)
        return _to_posix(rest)  # "skills\word-docx\create.py" → "skills/word-docx/create.py"

    # 已经是相对路径（含分隔符但不是绝对路径）→ 不动
    if ("/" in text or "\\" in text) and not _is_absolute_path(text):
        return None

    # 纯文件名 / 纯值 → 不动
    return None


def _tokenize_with_positions(command: str) -> list[tuple[int, int, str]]:
    """把命令拆成 token，同时记录每个 token 在原串中的 (start, end) 偏移。

    用于"原地替换路径 token"：只改需要改的区段，其余字符（含引号、空格）原样
    保留，避免 shlex.split→shlex.join 往返破坏引号语义（shlex.join 用 POSIX 单
    引号，但 Windows cmd.exe 不认单引号，会导致带空格的参数被切碎）。

    识别规则（轻量 shell 词法）：
    - 双引号 "..."、单引号 '...' 整体作为一个 token（引号内的分隔符不拆）；
    - 空白分隔；
    - && / || / ; / | / & / 换行 作为独立分隔 token（记录其位置，但不会被改写）。
    """
    tokens: list[tuple[int, int, str]] = []
    text = command
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c in " \t":
            i += 1
            continue
        # 链式分隔符
        if c == "\n":
            tokens.append((i, i + 1, "\n"))
            i += 1
            continue
        two = text[i : i + 2]
        if two in ("&&", "||"):
            tokens.append((i, i + 2, two))
            i += 2
            continue
        if c in (";", "|", "&"):
            tokens.append((i, i + 1, c))
            i += 1
            continue
        # 引号字符串或普通词
        start = i
        if c in ('"', "'"):
            quote = c
            i += 1
            while i < n and text[i] != quote:
                if quote == '"' and text[i] == "\\" and i + 1 < n:
                    i += 2
                    continue
                i += 1
            i += 1  # 跳过闭合引号（若有）
            tokens.append((start, i, text[start:i]))
        else:
            while i < n and text[i] not in " \t\n;&|":
                i += 1
            tokens.append((start, i, text[start:i]))
    return tokens


def _normalize_command_paths(command: str, root_dir: Path) -> str:
    """token 级路径改写：识别命令中的路径 token，原地替换为相对 root_dir 的路径。

    关键点（相比 lesso 全局 replace 的改进）：
    - 只改被识别为"路径 token"的词，JSON 字符串作为一个引号 token 整体保留，不破坏；
    - --out/--file 等输出路径参数的下一个 token 强制改写，不漏末尾路径；
    - 前缀从 root_dir 动态推导，不硬编码 C:/skills/；
    - **原地替换**（基于字符偏移），不重排/重引号，保留原命令的引号语义，避免
      Windows cmd.exe 不认 POSIX 单引号导致带空格参数被切碎。
    """
    root_posix = _to_posix(str(root_dir))
    root_win = str(root_dir)

    tokens = _tokenize_with_positions(command)
    if not tokens:
        return command

    # 收集要替换的 (start, end, new_text)，按 start 升序。最后从后往前替换避免偏移漂移。
    replacements: list[tuple[int, int, str]] = []
    force_next_path = False
    chain_seps = {"&&", "||", ";", "|", "&", "\n"}

    for start, end, raw in tokens:
        if raw in chain_seps:
            force_next_path = False  # 跨段重置
            continue

        # 剥引号得到 token 值
        if len(raw) >= 2 and raw[0] in ('"', "'") and raw[-1] == raw[0]:
            stripped_val = raw[1:-1]
            quote_char = raw[0]
        else:
            stripped_val = raw
            quote_char = ""

        # Windows 兼容：单引号字符串 → 双引号字符串。cmd.exe 不认单引号，会把
        # 'E2E Test' 切成 'E2E 和 Test' 两个参数。只有"需要引号"的 token（含空格/
        # 双引号/cmd 特殊字符）才转成双引号形式并转义内部双引号；纯无空格无特殊字符
        # 的词（如 'foo'）直接去引号更安全。
        # 注意：若该 token 同时是路径（会被下面改写为无引号相对路径），则跳过引号
        # 规范化，让路径改写接管，避免同一区段被替换两次。
        path_check = _rewrite_path_token(stripped_val, root_posix, root_win)
        if quote_char == "'" and path_check is None:
            # 需要引号的判定：空格、tab、双引号，以及 cmd.exe 元字符（% & < > ^ 等）。
            # 含双引号的 JSON 必须保留为带引号形式，否则 cmd.exe 会把裸 " 当特殊字符。
            needs_quote = bool(stripped_val == "" or re.search(r'[\s"`%&<>^|()]', stripped_val))
            if needs_quote:
                # 转成双引号，内部双引号用 \" 转义（cmd.exe / C runtime argv 解析兼容）
                escaped = stripped_val.replace('"', '\\"')
                replacements.append((start, end, f'"{escaped}"'))
            else:
                # 无空格无特殊字符：去引号即可（cmd.exe 下裸词更可靠）
                replacements.append((start, end, stripped_val))

        if force_next_path:
            rewritten = _rewrite_path_token(stripped_val, root_posix, root_win)
            if rewritten is not None:
                # 替换为不带引号的相对路径（相对路径无空格，安全；且 cmd.exe 友好）
                replacements.append((start, end, rewritten))
            force_next_path = False
            continue

        if stripped_val in _PATH_VALUE_FLAGS:
            force_next_path = True
            continue

        rewritten = _rewrite_path_token(stripped_val, root_posix, root_win)
        if rewritten is not None:
            replacements.append((start, end, rewritten))

    if not replacements:
        return command

    # 从后往前替换，避免偏移漂移
    result = command
    for start, end, new_text in sorted(replacements, key=lambda x: x[0], reverse=True):
        result = result[:start] + new_text + result[end:]
    return result


# ----------------------------- 编码 / 子进程环境 -----------------------------


def _path_under_subdir(resolved: Path, root: Path, subdir: str) -> bool:
    """判断 resolved 是否落在 root/subdir 子树内（用于写白名单 / skills 只读判定）。

    比较解析后的绝对路径，避免 `output/../skills/x.py` 这类相对越界绕过。
    """
    try:
        target_root = (root / subdir).resolve()
        resolved.relative_to(target_root)
        return True
    except (ValueError, OSError):
        return False


def _decode_shell_output(data: bytes | None) -> str:
    """utf-8 → gbk 双解码兜底（Windows 中文环境兼容）。"""
    if not data:
        return ""
    for encoding in ("utf-8", "gbk"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _build_skill_subprocess_env() -> dict[str, str]:
    """精简子进程环境：只放行安全键 + 强制 UTF-8。"""
    env: dict[str, str] = {}
    for key in _SAFE_SUBPROCESS_ENV_KEYS:
        value = os.environ.get(key)
        if value:
            env[key] = value
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


# ----------------------------- 内层：路径改写 + 编码 -----------------------------


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
        # 同步实现即可（subprocess.run 是阻塞的）；deepagents 在异步路径也会调用此方法。
        return self.execute(command, timeout=timeout)


# ----------------------------- 外层：白名单安全拦截 -----------------------------


def _is_virtual_posix_path(p: str) -> bool:
    """形如 /foo/bar 的 POSIX 虚拟路径（排除 //host、C:/、含反斜杠）。"""
    if not p or not p.startswith("/"):
        return False
    if p.startswith("//"):
        return False
    if "\\" in p:
        return False
    return True


def _path_stays_within_root(target: str, root: Path) -> bool:
    """判断路径 target（可能是相对/绝对/虚拟）解析后是否在 root 子树内。"""
    if not target:
        return True
    text = target.strip().strip('"').strip("'")
    if not text or text in {".", "/"}:
        return True
    # 相对路径：相对 root 解析
    if not _is_absolute_path(text) and not text.startswith("/"):
        try:
            resolved = (root / text).resolve()
            resolved.relative_to(root.resolve())
            return True
        except (ValueError, OSError):
            return False
    # 虚拟绝对 /skills/...：剥前导 / 后相对 root
    if _is_virtual_posix_path(text):
        try:
            resolved = (root / text.lstrip("/")).resolve()
            resolved.relative_to(root.resolve())
            return True
        except (ValueError, OSError):
            return False
    # 真绝对路径：必须在 root 子树内
    try:
        resolved = Path(text).resolve()
        resolved.relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


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
    elif reason == "not_in_allowlist" and command_head:
        output = (
            f"{_SHELL_DENIED_MARKER} 命令 `{command_head}` 不在白名单内，已被拦截。"
            "允许的命令：python/ls/dir/cat/type/head/tail/find/pwd/test/echo/cd/pushd/popd/chdir。"
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


def create_llm():
    """根据 .env 中的 LLM_PROVIDER 创建对应的 LLM 实例"""
    provider = os.getenv("LLM_PROVIDER", "agnes").lower()

    if provider == "deepseek":
        return ChatOpenAI(
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            api_key=os.getenv("DEEPSEEK_API_KEY"),
        )
    else:  # 默认 agnes
        return ChatOpenAI(
            model=os.getenv("AGNES_MODEL", "agnes-2.0-flash"),
            base_url=os.getenv("AGNES_BASE_URL", "https://apihub.agnes-ai.com/v1/chat/completions"),
            api_key=os.getenv("AGNES_API_KEY"),
        )


llm = create_llm()

SYSTEM_PROMPT = """你是权哥的助手，你叫做小权，你的任务是帮助权哥完成各种任务。

## 文件输出目录约定（必须遵守）
- **最终交付给用户的产物**（文档、表格、图片、导出文件等）一律写到 `output/` 目录。只有 `output/` 下的文件会被自动发送给用户。
- **中间过程文件**（临时草稿、下载的素材、调试输出、中间计算结果）一律写到 `tmp/` 目录。`tmp/` 下的文件不会发给用户，仅用于你自己的中间处理。
- 绝对不要把中间文件混进 `output/`，也不要把最终产物写到 `tmp/`。"""

# 确保 workspace 子目录存在
Path("workspace/tmp").mkdir(parents=True, exist_ok=True)
Path("workspace/output").mkdir(parents=True, exist_ok=True)

# 组装 backend：外层白名单 + 内层路径改写/编码。
_inner_backend = _SkillsShellBackend(root_dir="workspace", virtual_mode=True)
backend = _ShellWhitelistFilter(_inner_backend, skills_root=str(_inner_backend.cwd))

#去掉 interrupt_on
agent = create_deep_agent(
    model=llm,
    system_prompt=SYSTEM_PROMPT,
    backend=backend,
    tools=[web_search, get_current_time, render_html],
    checkpointer=MemorySaver(),
    skills=["skills/"],
)

langfuse = get_client()
langfuse_handler = CallbackHandler()


def new_thread_id(prefix: str = "thread") -> str:
    return f"{prefix}:{uuid.uuid4()}"
