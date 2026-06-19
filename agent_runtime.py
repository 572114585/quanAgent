"""
共享的 agent 运行时。

CLI（demo.py）保留不动；WeCom 渠道（run_wecom.py）从这里 import 同一个 agent。
注意：WeCom 没有 stdin，**不启用** interrupt_on={...}（HITL 在企业微信里会卡死）。
"""
import os
import uuid
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langfuse import get_client
from langfuse.langchain import CallbackHandler
from langgraph.checkpoint.memory import MemorySaver
from deepagents import create_deep_agent
from deepagents.backends import LocalShellBackend

from ducktools import web_search
from time_tools import get_current_time

load_dotenv()


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

SYSTEM_PROMPT = "你是权哥的助手，你叫做小权，你的任务是帮助权哥完成各种任务。"

#去掉 interrupt_on
agent = create_deep_agent(
    model=llm,
    system_prompt=SYSTEM_PROMPT,
    backend=LocalShellBackend(root_dir="workspace", virtual_mode=True, inherit_env=True),
    tools=[web_search, get_current_time],
    checkpointer=MemorySaver(),
    skills=["skills/"],
)

langfuse = get_client()
langfuse_handler = CallbackHandler()


def new_thread_id(prefix: str = "thread") -> str:
    return f"{prefix}:{uuid.uuid4()}"
