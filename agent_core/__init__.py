"""agent 核心装配包。

替代原根级 agent_runtime.py 的非沙箱部分。统一导出 agent 单例、build_agent 工厂、
LLM 工厂、系统提示词、子 agent 定义、配置常量。沙箱安全层在独立的 sandbox/ 包。

典型用法：
    from agent_core import agent, build_agent, create_llm, SYSTEM_PROMPT
    from agent_core import OUTPUT_DIR, UPLOADS_DIR, HITL_ENABLED_DEFAULT
"""
from agent_core.config import (
    AGENT_MODE_DEFAULT,
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
from agent_core.events import SCHEMA_VERSION, make_event
from agent_core.llm import (
    create_llm,
    get_llm_model_name,
    get_llm_provider,
    llm_supports_vision,
)
from agent_core.permissions import AgentMode, build_interrupt_on, resolve_permission
def __getattr__(name: str):
    """Delay runtime/LLM construction until an entrypoint explicitly needs it.

    This keeps schemas, permissions, and offline tests importable without an API key.
    """
    if name in {"agent", "build_agent", "new_thread_id"}:
        from agent_core import runtime

        return getattr(runtime, name)
    if name == "llm":
        from agent_core.llm import llm

        return llm
    if name in {"SYSTEM_PROMPT", "section_writer", "system_prompt_for"}:
        from agent_core import prompts

        return getattr(prompts, name)
    raise AttributeError(name)

__all__ = [
    "agent",
    "build_agent",
    "new_thread_id",
    "create_llm",
    "llm",
    "get_llm_provider",
    "get_llm_model_name",
    "llm_supports_vision",
    "SYSTEM_PROMPT",
    "system_prompt_for",
    "section_writer",
    "WORKSPACE_ROOT",
    "OUTPUT_DIR",
    "TMP_DIR",
    "SKILLS_DIR",
    "UPLOADS_DIR",
    "HITL_ENABLED_DEFAULT",
    "AGENT_MODE_DEFAULT",
    "MAX_UPLOAD_SIZE",
    "LOG_LEVEL",
    "ensure_runtime_dirs",
    "SCHEMA_VERSION",
    "make_event",
    "AgentMode",
    "resolve_permission",
    "build_interrupt_on",
]
