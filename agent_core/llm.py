"""LLM 工厂。

从原 agent_runtime.py L1240-1258 拆出。根据 .env 中的 LLM_PROVIDER 创建对应的
ChatOpenAI 实例（agnes / deepseek）。模块级 `llm` 单例保留，供直接复用。
"""
import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

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
