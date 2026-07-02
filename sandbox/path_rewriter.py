"""shlex 分词 + token 级路径改写辅助函数。

从原 agent_runtime.py L154-718 + L949-989 拆出。纯函数模块，不依赖 deepagents，
供 backend.py / whitelist.py 复用。包含：
- 命令分段 / head 提取（lesso 风格的引号感知分段）
- python/bash/curl 位置参数提取（脚本白名单校验用）
- token 级路径改写（虚拟绝对路径 / 盘符根路径 → 相对 root_dir）
- 编码兼容（utf-8/gbk 双解码）+ 子进程环境精简
"""
import glob as _glob
import logging
import os
import re
import shlex
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Iterable

from sandbox.constants import (
    _CHAIN_SEPARATORS,
    _CURL_ALLOWED_HOSTS,
    _PATH_VALUE_FLAGS,
    _SAFE_SUBPROCESS_ENV_KEYS,
    _SKILLS_SUBDIR,
)

logger = logging.getLogger(__name__)


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


# bash/sh 的选项语义比 python 简单：
# - 带值选项极少（-O <level>），且 web-video 的 scaffold.sh 等不使用；
# - 绝大多数是开关位（-e/-u/-x/-l 等 set -euo pipefail 风格）；
# - -- 是选项终止符，其后第一个 token 必为脚本路径。
# 因此保守策略：所有 - 开头 token 当选项跳过，遇 -- 终止扫描。
# 内联代码风险（-c/-s）在 _reject_if_disallowed 里单独拦截，这里只负责提取路径。
def _extract_bash_positional(segment: str) -> str | None:
    """从 `bash [opts] script.sh [args]` 段提取第一个位置参数（脚本路径）。

    跳过 bash 开关选项（-e/-u/-x/-l 等），遇到 -- 终止选项扫描。
    返回脚本 token 原样字符串（含引号则剥掉），无位置参数（如 `bash -c '...'`）返回 None。
    注意：-c/-s 的拦截在调用方 _reject_if_disallowed 做完，能走到这里的命令都不含 -c/-s。
    """
    tokens = _split_segment_tokens(segment)
    tokens = _tokens_after_env_assignments(tokens)
    if not tokens:
        return None
    # tokens[0] 是 bash/sh，从 [1:] 开始扫选项。
    i = 1
    n = len(tokens)
    while i < n:
        tok = tokens[i]
        # -- 是选项终止符：其后第一个 token 必为脚本路径
        if tok == "--":
            i += 1
            if i < n:
                tok = tokens[i]
                if len(tok) >= 2 and tok[0] in ('"', "'") and tok[-1] == tok[0]:
                    return tok[1:-1]
                return tok
            return None
        # 任何 - 开头都当选项跳过（保守：宁可误判选项也不误判成脚本）
        if tok.startswith("-"):
            i += 1
            continue
        # 第一个非选项 token = 脚本路径，剥外层引号
        if len(tok) >= 2 and tok[0] in ('"', "'") and tok[-1] == tok[0]:
            return tok[1:-1]
        return tok
    return None


def _extract_curl_urls(segment: str) -> list[str]:
    """从 `curl [opts] <url> [url...]` 段提取所有 URL 位置参数。

    curl 的位置参数（不以 - 开头的 token，或 -- 之后的 token）即 URL。
    带值选项（-o/-d/-H/-X/-A 等）的下一个 token 是值不是 URL，要跳过。
    返回 URL token 原样字符串（剥外层引号），用于后续 host 白名单校验。
    """
    # curl 常见带值选项（下一个 token 是值，不是 URL）。
    # 覆盖 web-video openai.sh 用到的 -o/-d/-H/-X，以及其它常见 -A/-e/-u/-b/-c。
    curl_value_options = frozenset({
        "-o", "--output", "-d", "--data", "--data-raw", "--data-binary",
        "-H", "--header", "-X", "--request", "-A", "--user-agent",
        "-e", "--referer", "-u", "--user", "-b", "--cookie", "-c",
        "--cookie-jar", "-K", "--config", "--resolve", "--connect-to",
        "-w", "--write-out", "-m", "--max-time", "--retry",
    })
    tokens = _split_segment_tokens(segment)
    tokens = _tokens_after_env_assignments(tokens)
    urls: list[str] = []
    i = 1  # tokens[0] 是 curl
    n = len(tokens)
    after_double_dash = False
    while i < n:
        tok = tokens[i]
        if after_double_dash:
            stripped = tok[1:-1] if len(tok) >= 2 and tok[0] in ('"', "'") and tok[-1] == tok[0] else tok
            urls.append(stripped)
            i += 1
            continue
        if tok == "--":
            after_double_dash = True
            i += 1
            continue
        if tok in curl_value_options:
            i += 2  # 跳过选项和它的值
            continue
        # 形如 --opt=value 的长选项：单 token，跳过
        if tok.startswith("--") and "=" in tok:
            i += 1
            continue
        if tok.startswith("-"):
            i += 1
            continue
        # 位置参数 = URL
        stripped = tok[1:-1] if len(tok) >= 2 and tok[0] in ('"', "'") and tok[-1] == tok[0] else tok
        urls.append(stripped)
        i += 1
    return urls


def _curl_urls_allowed(urls: list[str]) -> tuple[bool, str | None]:
    """校验 curl 的所有 URL 是否都命中 host 白名单。

    返回 (是否放行, 第一个被拒的 URL)。空 URL 列表视为放行（curl 不发请求）。
    解析 URL 用 urllib，兼容 http/https，host 大小写不敏感比对。
    """
    if not urls:
        return True, None
    from urllib.parse import urlsplit

    for url in urls:
        try:
            host = urlsplit(url).hostname or ""
        except ValueError:
            return False, url
        if host.lower() not in _CURL_ALLOWED_HOSTS:
            return False, url
    return True, None


def _build_default_allow_pattern(commands: Iterable[str]) -> re.Pattern[str]:
    alternatives = "|".join(re.escape(cmd) for cmd in sorted(set(commands)))
    if not alternatives:
        return re.compile(r"^$")
    return re.compile(rf"^(?:{alternatives})$")


def _discover_skill_scripts(root: Path) -> frozenset[str]:
    """启动时 glob `<root>/skills/*/scripts/*.{py,sh}`，返回相对 root 的 POSIX 路径集合。

    这是 execute 脚本白名单的来源——deepagents 无 skills 脚本注册表，必须自己扫。
    每次启动重新扫，所以新增 skill 脚本重启即生效（无需改代码）。

    同时扫 .py 和 .sh：
    - .py：word-docx / excel-xlsx 等现有 skill 的脚本。
    - .sh：web-video-presentation 的 scaffold.sh / synthesize-audio.sh / pack.sh 等。
    """
    scripts_dir = root / _SKILLS_SUBDIR
    if not scripts_dir.is_dir():
        return frozenset()
    found: set[str] = set()
    for pattern in ("*/scripts/*.py", "*/scripts/*.sh"):
        for p in scripts_dir.glob(pattern):
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
    # 确保 Node.js 在 PATH 中：扫描常见安装路径，找到就追加。
    # agent_core 的子进程可能继承不到系统 PATH 里的 node，
    # 尤其在虚拟环境 / IDE 内嵌终端下。
    _node_candidates = [
        r"D:\nodejs",                              # 本机实际安装路径
        r"C:\Program Files\nodejs",                # 默认安装路径
        os.path.expanduser(r"~\AppData\Roaming\nvm\v*"),  # nvm-windows
    ]
    existing_path = env.get("PATH", "")
    existing_dirs = set(existing_path.split(os.pathsep))
    for candidate in _node_candidates:
        # 支持 glob 模式（nvm 路径含版本号）
        if "*" in candidate:
            matches = sorted(_glob.glob(candidate), reverse=True)
            for m in matches:
                node_exe = os.path.join(m, "node.exe")
                if os.path.isfile(node_exe) and m not in existing_dirs:
                    existing_dirs.add(m)
                    existing_path = m + os.pathsep + existing_path
            continue
        node_exe = os.path.join(candidate, "node.exe")
        if os.path.isfile(node_exe) and candidate not in existing_dirs:
            existing_dirs.add(candidate)
            existing_path = candidate + os.pathsep + existing_path
    env["PATH"] = existing_path
    return env


# ----------------------------- 虚拟路径 / 越界判定 -----------------------------


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
