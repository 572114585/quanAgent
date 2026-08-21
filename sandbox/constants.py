"""沙箱安全层的常量定义。

从原 agent_runtime.py L60-152 拆出。包含命令白名单、拦截模式、路径标记、
子进程环境白名单等。这些常量被 path_rewriter / backend / whitelist 共享。
"""
import re

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
    # PPT Master only receives the dedicated domestic image and visual-review
    # credentials.  Do not pass the primary LLM provider's general secrets.
    "PPT_VISION_MODEL",
    "PPT_VISION_TIMEOUT",
    "PPT_VISION_MAX_TOKENS",
    "PPT_IMAGE_MODEL",
    "SILICONFLOW_API_KEY",
    "SILICONFLOW_BASE_URL",
    "AGENT_API_KEY",
    "ARK_AGENT_PLAN_BASE_URL",
    "VOLCENGINE_OUTPUT_FORMAT",
    "IMAGE_BACKEND",
    "PPT_ALLOWED_IMAGE_BACKENDS",
    "IMAGE_CONCURRENCY",
    # upload-to-moss skill 子进程需要读到桶配置；WORKSPACE_ROOT 避免 cwd=workspace 时相对路径错一层。
    "WORKSPACE_ROOT",
    "MOSS_ENDPOINT",
    "MOSS_REGION",
    "MOSS_BUCKET",
    "MOSS_UPLOAD_BUCKET",
    "MOSS_ACCESS_KEY",
    "MOSS_SECRET_KEY",
    "MOSS_KEY_PREFIX",
)
# 命令形态级删除检测。该策略只识别命令头/子命令，不解析脚本或解释器
# 内部调用的文件系统 API（例如 Python 的 Path.unlink）。
_DELETE_COMMAND_HEADS: frozenset[str] = frozenset(
    {
        "rm",
        "rmdir",
        "unlink",
        "shred",
        "srm",
        "del",
        "erase",
        "rd",
        "remove-item",
        "ri",
    }
)
_DELETE_SUBCOMMANDS: dict[str, frozenset[str]] = {
    "find": frozenset({"-delete", "-delete-all"}),
    "git": frozenset({"clean"}),
    "npm": frozenset({"uninstall", "remove", "rm"}),
    "yarn": frozenset({"remove"}),
    "pnpm": frozenset({"remove", "rm", "uninstall"}),
    "bun": frozenset({"remove", "rm", "uninstall"}),
    "pip": frozenset({"uninstall"}),
    "pip3": frozenset({"uninstall"}),
    "pipx": frozenset({"uninstall"}),
    "uv": frozenset({"remove", "uninstall"}),
    "poetry": frozenset({"remove"}),
    "conda": frozenset({"remove", "uninstall"}),
    "cargo": frozenset({"remove"}),
    "docker": frozenset({"rm", "rmi"}),
    "kubectl": frozenset({"delete"}),
}
# 兼容旧路径重写工具的 curl host 集合；execute 删除策略不使用该集合限制出网。
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
_SKILL_SCRIPTS_GLOB = "skills/*/scripts/**/*.py"
