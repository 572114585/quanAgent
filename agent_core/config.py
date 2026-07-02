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

# 运行时开关（原 run.py L93/96 的 HITL_ENABLED / MAX_UPLOAD_SIZE）
HITL_ENABLED_DEFAULT = os.getenv("HITL_ENABLED", "true").lower() in ("1", "true", "yes")
MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", str(20 * 1024 * 1024)))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")


def ensure_runtime_dirs() -> None:
    """启动时确保 workspace/tmp、workspace/output 存在。

    替代原 agent_runtime.py L1293-1294 的模块级 mkdir 调用，改由 build_agent()
    显式触发，避免 mere import 即产生副作用。
    """
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
