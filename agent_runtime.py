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
from deepagents.backends import FilesystemBackend

from ducktools import web_search
from time_tools import get_current_time

load_dotenv()

llm = ChatOpenAI(
    model="agnes-2.0-flash",
    base_url="https://apihub.agnes-ai.com/v1/chat/completions",
    api_key=os.getenv("OPENAI_API_KEY"),
)

SYSTEM_PROMPT = "你是权哥的助手，你叫做小权，你的任务是帮助权哥完成各种任务。"

# WeCom 入口：去掉 interrupt_on
agent = create_deep_agent(
    model=llm,
    system_prompt=SYSTEM_PROMPT,
    backend=FilesystemBackend(root_dir="workspace", virtual_mode=True),
    tools=[web_search, get_current_time],
    checkpointer=MemorySaver(),
)

langfuse = get_client()
langfuse_handler = CallbackHandler()


def new_thread_id(prefix: str = "thread") -> str:
    return f"{prefix}:{uuid.uuid4()}"
