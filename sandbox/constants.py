"""沙箱安全层的常量定义。

从原 agent_runtime.py L60-152 拆出。包含命令白名单、拦截模式、路径标记、
子进程环境白名单等。这些常量被 path_rewriter / backend / whitelist 共享。
"""
import re

# 默认放行的 shell 命令白名单。
# - python/python3：跑 skill 脚本必需（-c/-m 被单独拦截防内联代码）。
# - 只读探查类（ls/dir/cat/type/head/tail/find/pwd/test/echo）：模型探查目录结构用，
#   无写入/网络副作用，物理工作目录受 root_dir 锁定。
# - 目录切换类（cd/pushd/popd/chdir）：目标经路径改写后必须在 root_dir 子树内，
#   越界由 cd 沙箱校验拦截。
# workspace_auto 下与 execute_policy 对齐的只读/探查 head；
# 软白名单仍作 strict 兜底；HITL 批准或 classification=auto 时可绕过。
DEFAULT_ALLOWED_COMMANDS: frozenset[str] = frozenset(
    {
        "python",
        "python3",
        "py",
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
        "wc",
        "grep",
        "findstr",
        "rg",
        "sort",
        "uniq",
        "tr",
        "cut",
        "date",
        "whoami",
        "hostname",
        "which",
        "where",
        "tree",
        "git",
        "pytest",
        "ruff",
        "mypy",
        "black",
        "tsc",
        "vue-tsc",
        "eslint",
        "prettier",
        "make",
    }
)

# 拦截的命令替换语法：反引号、$()。
_COMMAND_SUBSTITUTION_PATTERN = re.compile(r"`|\$\(")
# 极危险命令硬拒绝（HITL 批准也不可绕过）。对齐 grok-build：deny 优先于审批。
_HARD_DENY_PATTERNS: tuple[re.Pattern[str], ...] = (
    # rm -rf / 或 rm -rf /*（\b 在 / 后不可靠，改用空白或行尾）
    re.compile(r"\brm\s+-[a-zA-Z]*[rf][a-zA-Z]*[rf][a-zA-Z]*\s+(/|/\*)(?:\s|$)", re.I),
    re.compile(r"\b(format|mkfs)\b", re.I),
    re.compile(r"\bdd\s+.*\bof=/dev/", re.I),
)
# python 危险选项：-c（内联代码）、-m（模块）、-（stdin）。
_PYTHON_BLOCKED_OPTIONS = frozenset({"-c", "-m", "-"})
# bash/sh 危险选项：-c（内联代码）、-s（从 stdin 执行）、-（stdin）。
# 与 _PYTHON_BLOCKED_OPTIONS 同理，阻止内联代码绕过脚本白名单。
_BASH_BLOCKED_OPTIONS = frozenset({"-c", "-s", "-"})
# 引号外的链式命令分隔符。
_CHAIN_SEPARATORS: frozenset[str] = frozenset({"&&", "||", ";", "|", "&", "\n"})
# 命令中显式指定 cwd 的常见模式：cd /xxx、pushd /xxx、chdir /xxx。
_CD_PATTERN = re.compile(r"\b(?:cd|pushd|chdir)\s+(?P<target>[^\s;&|]+)")
# 子进程环境白名单：只放行这些键（其余不继承），再强制 UTF-8。
# 业务键（OPENAI_*）为 web-video-presentation 的 TTS 子进程保留；
# HOME/USERPROFILE 是 npm 解析 .npmrc / 缓存目录所需。
_SAFE_SUBPROCESS_ENV_KEYS: tuple[str, ...] = (
    "PATH",
    "SystemRoot",
    "WINDIR",
    "COMSPEC",
    "PATHEXT",
    "TEMP",
    "TMP",
    "HOME",
    "USERPROFILE",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "OPENAI_TTS_MODEL",
    # MinerU 文档提取 skill:extract 模式需要 token(.env 中为 MINERU_API_TOKEN)。
    # CLI 文档变量名为 MINERU_TOKEN,一并放行以兼容。
    "MINERU_API_TOKEN",
    "MINERU_TOKEN",
)
# Node 构建链命令：web-video-presentation 等 Node skill 需要。
# 不并入 DEFAULT_ALLOWED_COMMANDS（保持默认收紧），由调用方按需合并传入。
_NODE_BUILD_COMMANDS: frozenset[str] = frozenset(
    {"npm", "npx", "node", "bash", "sh", "jq", "curl", "zip"}
)
# curl 出网 host 白名单：只放行 OpenAI TTS API（web-video-presentation 内置 provider）。
# 其它 host 一律拒，避免 curl 成为通用出网口子。新增 TTS 后端时在此追加。
_CURL_ALLOWED_HOSTS: frozenset[str] = frozenset(
    {"api.openai.com"}
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
