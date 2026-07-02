"""agent 核心装配包。

替代原根级 agent_runtime.py 的非沙箱部分。统一导出 agent 单例、build_agent 工厂、
LLM 工厂、系统提示词、子 agent 定义、配置常量。沙箱安全层在独立的 sandbox/ 包。

典型用法：
    from agent_core import agent, build_agent, create_llm, SYSTEM_PROMPT
    from agent_core import OUTPUT_DIR, UPLOADS_DIR, HITL_ENABLED_DEFAULT
"""
from agent_core.config import (
    HITL_ENABLED_DEFAULT,
    LOG_LEVEL,
    MAX_UPLOAD_SIZE,
    OUTPUT_DIR,
    SKILLS_DIR,
    TMP_DIR,
    UPLOADS_DIR,
    WORKSPACE_ROOT,
    ensure_runtime_dirs,
)
from agent_core.llm import create_llm, llm
from agent_core.prompts import SYSTEM_PROMPT, research_subagent
from agent_core.runtime import agent, build_agent, new_thread_id

__all__ = [
    "agent",
    "build_agent",
    "new_thread_id",
    "create_llm",
    "llm",
    "SYSTEM_PROMPT",
    "research_subagent",
    "WORKSPACE_ROOT",
    "OUTPUT_DIR",
    "TMP_DIR",
    "SKILLS_DIR",
    "UPLOADS_DIR",
    "HITL_ENABLED_DEFAULT",
    "MAX_UPLOAD_SIZE",
    "LOG_LEVEL",
    "ensure_runtime_dirs",
]
