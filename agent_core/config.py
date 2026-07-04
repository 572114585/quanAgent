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

# 运行时开关（原 run.py L93/96 的 HITL_ENABLED / MAX_UPLOAD_SIZE）
HITL_ENABLED_DEFAULT = os.getenv("HITL_ENABLED", "true").lower() in ("1", "true", "yes")
MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", str(20 * 1024 * 1024)))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# ===== 搜索 Provider 配置 =====
# 三个第三方搜索 API 的 key,留空则该 provider 不启用(直接跳过,不入 failover 链路)。
# 链路顺序:Tavily → Brave → Serper → DuckDuckGo(兜底)
TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
BRAVE_API_KEY: str = os.getenv("BRAVE_API_KEY", "")
SERPER_API_KEY: str = os.getenv("SERPER_API_KEY", "")
# provider 额度耗尽后冷却时间(秒),默认 1 小时
SEARCH_PROVIDER_COOLDOWN_SECONDS: int = int(os.getenv("SEARCH_PROVIDER_COOLDOWN_SECONDS", "3600"))


def ensure_runtime_dirs() -> None:
    """启动时确保 workspace/tmp、workspace/output、workspace/state 存在。

    替代原 agent_runtime.py L1293-1294 的模块级 mkdir 调用，改由 build_agent()
    显式触发，避免 mere import 即产生副作用。
    """
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
