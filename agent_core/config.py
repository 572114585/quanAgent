"""统一配置层：跨模块共享的路径常量与运行时开关。

消除原先散落在 agent_runtime.py / html_tools.py / run.py / channels/wechat/bridge.py
各处的 "workspace" 魔法字符串与重复的 os.getenv 调用。所有路径常量在此集中，
其余模块从此导入。channel 专属配置（WechatConfig/WeComConfig）仍保留在各自
channels/<name>/config.py，不并入此处。
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# agent 沙箱根目录。保持字面值 "workspace"（与原 agent_runtime.py 的 root_dir 一致）。
WORKSPACE_ROOT = Path(os.getenv("WORKSPACE_ROOT", "workspace"))
OUTPUT_DIR = WORKSPACE_ROOT / "output"
TMP_DIR = WORKSPACE_ROOT / "tmp"
SKILLS_DIR = WORKSPACE_ROOT / "skills"
UPLOADS_DIR = WORKSPACE_ROOT / "uploads"

# checkpointer 持久化目录与 DB 文件（task plan / messages / interrupts 落库位置）。
# 与 output/tmp/uploads 同级，随 workspace 卷一起持久化，进程重启后 thread 状态可恢复。
STATE_DIR = WORKSPACE_ROOT / "state"
CHECKPOINT_DB_PATH = STATE_DIR / "checkpoints.sqlite"
# 流式事件 append-only 日志（SSE 断线补流）
EVENT_LOG_DB_PATH = STATE_DIR / "events.sqlite"

# 运行预算：LangGraph recursion_limit 与单次 run 墙钟超时
AGENT_RECURSION_LIMIT = int(os.getenv("AGENT_RECURSION_LIMIT", "100"))
AGENT_RUN_DEADLINE_SECONDS = float(os.getenv("AGENT_RUN_DEADLINE_SECONDS", "1800"))

# 运行时开关（原 run.py L93/96 的 HITL_ENABLED / MAX_UPLOAD_SIZE）
HITL_ENABLED_DEFAULT = os.getenv("HITL_ENABLED", "true").lower() in ("1", "true", "yes")
MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", str(20 * 1024 * 1024)))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Agent 模式与权限（详见 agent_core.permissions / execute_policy）
# AGENT_MODE=agent|plan ；PERMISSION_EXECUTE / PERMISSION_WRITE = allow|ask|deny
# EXECUTE_PROFILE=workspace_auto|manual
#   workspace_auto（默认）：只读/构建自动执行；解释器内联/联网/安装需确认
#   manual：每条 execute 都 ask（旧行为）
# 默认：WRITE=allow，EXECUTE 按命令分类（工具级仍为 ask + when 谓词）
AGENT_MODE_DEFAULT = os.getenv("AGENT_MODE", "agent").strip().lower()
if AGENT_MODE_DEFAULT not in ("agent", "plan"):
    AGENT_MODE_DEFAULT = "agent"
EXECUTE_PROFILE_DEFAULT = os.getenv("EXECUTE_PROFILE", "workspace_auto").strip().lower()
if EXECUTE_PROFILE_DEFAULT not in ("workspace_auto", "manual", "ask_all", "legacy"):
    EXECUTE_PROFILE_DEFAULT = "workspace_auto"
CHANNEL_DENY_EXECUTE = os.getenv("CHANNEL_DENY_EXECUTE", "true").lower() in (
    "1", "true", "yes",
)
# 可选脚本 hooks 目录（相对 WORKSPACE_ROOT 或绝对路径）
HOOKS_DIR = Path(os.getenv("HOOKS_DIR", str(WORKSPACE_ROOT / "hooks")))

# ===== Web 控制面 =====
# Bearer Token；未设置时仅建议在回环地址无鉴权使用
AGENT_API_TOKEN: str = os.getenv("AGENT_API_TOKEN", "").strip()
# CORS 允许来源（逗号分隔）
_DEFAULT_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
ALLOWED_ORIGINS: list[str] = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", _DEFAULT_ORIGINS).split(",")
    if o.strip()
]
# 监听地址；默认仅本机
WEB_HOST_DEFAULT = "127.0.0.1"
# ===== 搜索 Provider 配置 =====
# 三个第三方搜索 API 的 key,留空则该 provider 不启用(直接跳过,不入 failover 链路)。
# 链路顺序:Tavily → Brave → Serper → DuckDuckGo(兜底)
TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
BRAVE_API_KEY: str = os.getenv("BRAVE_API_KEY", "")
SERPER_API_KEY: str = os.getenv("SERPER_API_KEY", "")
# provider 额度耗尽后冷却时间(秒),默认 1 小时
SEARCH_PROVIDER_COOLDOWN_SECONDS: int = int(os.getenv("SEARCH_PROVIDER_COOLDOWN_SECONDS", "3600"))

# 注意:知识库(kb_tool)的 KB_* 配置不在此处定义,统一在 tools/kb_tool.py 读取。
# 原因:agent_core 包初始化会拉 runtime → build_agent → 需要 tools,若 kb_tool
# 从此处 import 会形成循环。此处只在 ensure_runtime_dirs 中确保持久化目录存在。


def ensure_runtime_dirs() -> None:
    """启动时确保 workspace/tmp、workspace/output、workspace/state 存在。

    替代原 agent_runtime.py L1293-1294 的模块级 mkdir 调用，改由 build_agent()
    显式触发，避免 mere import 即产生副作用。
    """
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    # 知识库持久化目录(KB_* 配置见 tools/kb_tool.py,此处只读 env 确保 mkdir)
    kb_persist_dir = os.getenv("KB_PERSIST_DIR", str(WORKSPACE_ROOT / "kb_store"))
    Path(kb_persist_dir).mkdir(parents=True, exist_ok=True)
